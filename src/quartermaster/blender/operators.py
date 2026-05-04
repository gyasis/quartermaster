"""Blender operators exposing Quartermaster actions to the user."""
from __future__ import annotations
import bpy
from mathutils import Vector

from ..joint_strategy import JointSpec, JointType, pick_joint
from ..joints.preview import joint_preview
from .adapter import add_cut_plane_helper, cut_plane_from_empty, QM_CUT_PLANE_PROP
from .cut import cut_along_plane
from .fixtures import create_test_block

QM_PREVIEW_NAME = "QM_JointPreview"


def _find_cut_plane():
    return next((o for o in bpy.data.objects if o.get(QM_CUT_PLANE_PROP)), None)


def _world_aabb(obj):
    """Return (bbox_min, bbox_max) in world space for the object's evaluated mesh."""
    deps = bpy.context.evaluated_depsgraph_get()
    ev = obj.evaluated_get(deps)
    ev_mesh = ev.to_mesh()
    if not ev_mesh.vertices:
        ev.to_mesh_clear()
        return None, None
    verts_w = [obj.matrix_world @ v.co for v in ev_mesh.vertices]
    ev.to_mesh_clear()
    xs = [v.x for v in verts_w]
    ys = [v.y for v in verts_w]
    zs = [v.z for v in verts_w]
    return Vector((min(xs), min(ys), min(zs))), Vector((max(xs), max(ys), max(zs)))


# --- Quick-start fixtures ----------------------------------------------------

class QM_OT_AddTestBlock(bpy.types.Operator):
    """Drop a clean 300x200x4mm cuboid at the origin to test the cut pipeline."""
    bl_idname = "quartermaster.add_test_block"
    bl_label = "Add Test Block"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        block = create_test_block(name="QM_TestBlock", size=(300.0, 200.0, 4.0), location=(0.0, 0.0, 0.0))
        bpy.ops.object.select_all(action="DESELECT")
        block.select_set(True)
        context.view_layer.objects.active = block
        self.report({"INFO"}, f"Added {block.name} (300x200x4mm) — picker target: scarf 8:1")
        return {"FINISHED"}


class QM_OT_AddDovetailBlock(bpy.types.Operator):
    """Drop a clean 80x60x6mm cuboid — picker target for this block is DOVETAIL (single tail)."""
    bl_idname = "quartermaster.add_dovetail_block"
    bl_label = "Add Dovetail Block"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        block = create_test_block(name="QM_DovetailBlock", size=(80.0, 60.0, 6.0), location=(0.0, 0.0, 0.0))
        bpy.ops.object.select_all(action="DESELECT")
        block.select_set(True)
        context.view_layer.objects.active = block
        self.report({"INFO"}, f"Added {block.name} (80x60x6mm) — picker target: dovetail")
        return {"FINISHED"}


# --- Cut plane management ----------------------------------------------------

class QM_OT_AddCutPlane(bpy.types.Operator):
    """Drop a draggable cut-plane Empty into the scene. Local +Z is the cut \
normal; local +Y is the seam direction."""
    bl_idname = "quartermaster.add_cut_plane"
    bl_label = "Add Cut Plane"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        location = tuple(context.scene.cursor.location)
        ob = context.active_object
        if ob and ob.type == "MESH" and not ob.get(QM_CUT_PLANE_PROP):
            mn, mx = _world_aabb(ob)
            if mn is not None:
                location = tuple((mn + mx) * 0.5)

        empty = add_cut_plane_helper(name="QM_CutPlane", location=location, size=120.0)
        bpy.ops.object.select_all(action="DESELECT")
        empty.select_set(True)
        context.view_layer.objects.active = empty

        try:
            bpy.ops.wm.tool_set_by_id(name="builtin.transform")
        except (RuntimeError, TypeError):
            pass
        for area in context.screen.areas:
            if area.type == "VIEW_3D":
                for space in area.spaces:
                    if space.type == "VIEW_3D":
                        space.show_gizmo = True
                        space.show_gizmo_object_translate = True
                        space.show_gizmo_object_rotate = True

        self.report({"INFO"}, f"Added {empty.name} — drag the gizmo arrows to position")
        return {"FINISHED"}


class QM_OT_SnapCutPlane(bpy.types.Operator):
    """Position the cut plane to bisect the active mesh perpendicular to its longest axis."""
    bl_idname = "quartermaster.snap_cut_plane"
    bl_label = "Snap to Longest Axis"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        ob = context.active_object
        if ob is None or ob.type != "MESH" or ob.get(QM_CUT_PLANE_PROP):
            return False
        return _find_cut_plane() is not None

    def execute(self, context):
        target = context.active_object
        plane = _find_cut_plane()
        mn, mx = _world_aabb(target)
        if mn is None:
            self.report({"ERROR"}, "Active mesh has no geometry")
            return {"CANCELLED"}
        size = mx - mn
        center = (mn + mx) * 0.5

        longest_idx = max(range(3), key=lambda i: size[i])
        z_target = Vector((0.0, 0.0, 0.0))
        z_target[longest_idx] = 1.0

        plane.location = center
        plane.rotation_mode = "QUATERNION"
        plane.rotation_quaternion = Vector((0, 0, 1)).rotation_difference(z_target)
        bpy.context.view_layer.update()

        axis = "XYZ"[longest_idx]
        self.report(
            {"INFO"},
            f"Snapped cut plane to {axis} axis (length {size[longest_idx]:.1f}mm) at {tuple(round(c, 1) for c in center)}",
        )
        return {"FINISHED"}


# --- The cut itself ---------------------------------------------------------

def _build_override_spec(scene) -> "JointSpec | None":
    """Translate scene properties into a JointSpec override (or None for AUTO)."""
    mode = getattr(scene, "qm_joint_override", "AUTO")
    if mode == "AUTO":
        return None
    if mode == "DOVETAIL":
        return JointSpec(
            JointType.DOVETAIL,
            {
                "angle_deg":  scene.qm_dovetail_angle,
                "tail_count": scene.qm_tail_count,
            },
            pin_count=0,
            rationale="user override (panel)",
        )
    if mode == "HALF_LAP":
        return JointSpec(
            JointType.HALF_LAP,
            {"overlap_mm": scene.qm_overlap_mm},
            pin_count=0,
            rationale="user override (panel)",
        )
    if mode == "SLIDING_DOVETAIL":
        # depth/base_width default from generator; user controls angle
        return JointSpec(
            JointType.SLIDING_DOVETAIL,
            {"angle_deg": scene.qm_dovetail_angle},
            pin_count=0,
            rationale="user override (panel)",
        )
    return None


class QM_OT_ExecuteCut(bpy.types.Operator):
    """Cut the active mesh along the QM_CutPlane Empty using picker-chosen joinery."""
    bl_idname = "quartermaster.execute_cut"
    bl_label = "Cut Along Plane"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        ob = context.active_object
        if ob is None or ob.type != "MESH":
            return False
        return _find_cut_plane() is not None

    def execute(self, context):
        target = context.active_object
        plane = _find_cut_plane()
        if plane is None:
            self.report({"ERROR"}, "No QM_CutPlane in scene — click 'Add Cut Plane' first")
            return {"CANCELLED"}

        for suffix in ("_L", "_R", "_baked"):
            if target.name.endswith(suffix):
                source = bpy.data.objects.get(target.name[: -len(suffix)])
                if source and source.type == "MESH":
                    self.report(
                        {"INFO"},
                        f"Redirecting from derivative {target.name} to source {source.name}",
                    )
                    target = source
                    break

        # Multi-object union: any other selected mesh that isn't the target,
        # a cut plane, or a derivative of the target (avoid unioning a previous
        # _L/_R back into the source after a redirect).
        extras = [
            o for o in context.selected_objects
            if o is not target
            and o.type == "MESH"
            and not o.get(QM_CUT_PLANE_PROP)
            and not o.name.startswith(target.name + "_")
        ]

        try:
            result = cut_along_plane(
                target, plane,
                table_mm=getattr(context.scene, "qm_table_mm", 0.0),
                tolerance_mm=getattr(context.scene, "qm_tolerance_mm", 0.0),
                override_spec=_build_override_spec(context.scene),
                extra_meshes=extras or None,
            )
        except Exception as exc:
            self.report({"ERROR"}, f"Cut failed: {exc}")
            return {"CANCELLED"}

        table = result.spec.params.get("table_mm", 0)
        variant = f" + table {table:.1f}mm" if table else ""
        union_note = f" (+{len(extras)} unioned)" if extras else ""
        self.report(
            {"INFO"},
            f"{result.spec.joint.value.upper()}{variant}{union_note}: "
            f"t={result.thickness:.1f}mm seam={result.seam_length:.0f}mm pins={result.spec.pin_count}",
        )
        return {"FINISHED"}


def _measure_target(target, plane_empty):
    """Return (thickness, seam_length) for the active target, or (None, None)
    if there's no usable mesh."""
    if target is None or target.type != "MESH" or target.get(QM_CUT_PLANE_PROP):
        return None, None
    base_plane = cut_plane_from_empty(plane_empty)
    deps = bpy.context.evaluated_depsgraph_get()
    ev = target.evaluated_get(deps)
    ev_mesh = ev.to_mesh()
    if not ev_mesh.vertices:
        ev.to_mesh_clear()
        return None, None
    verts_w = [target.matrix_world @ v.co for v in ev_mesh.vertices]
    ev.to_mesh_clear()
    xs = [v.x for v in verts_w]; ys = [v.y for v in verts_w]; zs = [v.z for v in verts_w]
    bbox_min = (min(xs), min(ys), min(zs))
    bbox_max = (max(xs), max(ys), max(zs))
    return base_plane.measure(bbox_min, bbox_max)


class QM_OT_PreviewJoint(bpy.types.Operator):
    """Show a wireframe preview of the current joint at the cut plane location.

    The preview is a Blender object whose edges trace the joint's cut path.
    It updates whenever you click — change the joint, click again to see it.
    """
    bl_idname = "quartermaster.preview_joint"
    bl_label  = "Preview Joint"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        return _find_cut_plane() is not None

    def execute(self, context):
        plane = _find_cut_plane()
        target = context.active_object
        # Skip the preview itself if it's active
        if target is not None and target.name == QM_PREVIEW_NAME:
            target = None
        thickness, seam_length = _measure_target(target, plane)
        if thickness is None:
            # No target — pick representative defaults so the user still sees
            # the joint shape
            thickness, seam_length = 4.0, 200.0

        spec = _build_override_spec(context.scene)
        if spec is None:
            spec = pick_joint(thickness=thickness, seam_length=seam_length)
        # Apply table_mm if set (matches what cut_along_plane does for SCARF)
        table_mm = getattr(context.scene, "qm_table_mm", 0.0)
        if table_mm > 0 and spec.joint == JointType.SCARF:
            spec = JointSpec(
                joint=spec.joint,
                params={**spec.params, "table_mm": table_mm},
                pin_count=spec.pin_count,
                rationale=spec.rationale + f" | table {table_mm:.1f}mm",
            )

        try:
            preview = joint_preview(spec, thickness=thickness, seam_length=seam_length)
        except NotImplementedError as exc:
            self.report({"ERROR"}, f"Preview not available: {exc}")
            return {"CANCELLED"}

        _make_preview_object(plane, preview, name=QM_PREVIEW_NAME)
        self.report({"INFO"}, f"Preview: {preview.description}")
        return {"FINISHED"}


def _make_preview_object(plane_empty, preview, name):
    """Create or replace a wireframe-only Blender object showing the joint preview."""
    import bmesh
    from mathutils import Vector

    base_plane = cut_plane_from_empty(plane_empty)
    n_axis = Vector(base_plane.normal).normalized()
    s_axis = Vector(base_plane.seam_axis).normalized()
    t_axis = n_axis.cross(s_axis).normalized()
    p0     = Vector(base_plane.point)

    if preview.axes == "n_t":
        axis_x, axis_y = n_axis, t_axis
    else:
        axis_x, axis_y = n_axis, s_axis

    # Replace any prior preview
    if name in bpy.data.objects:
        bpy.data.objects.remove(bpy.data.objects[name], do_unlink=True)

    bm = bmesh.new()
    for (a, b) in preview.lines_2d:
        v1 = bm.verts.new(p0 + axis_x * a[0] + axis_y * a[1])
        v2 = bm.verts.new(p0 + axis_x * b[0] + axis_y * b[1])
        bm.edges.new([v1, v2])
    # Merge coincident endpoints so shared corners draw once
    bmesh.ops.remove_doubles(bm, verts=bm.verts[:], dist=1e-5)

    mesh = bpy.data.meshes.new(f"{name}_mesh")
    bm.to_mesh(mesh)
    bm.free()
    obj = bpy.data.objects.new(name, mesh)
    obj.show_in_front = True
    obj.show_wire     = True
    obj.display_type  = "WIRE"
    bpy.context.collection.objects.link(obj)
    return obj


class QM_OT_ResetScene(bpy.types.Operator):
    """Remove all Quartermaster-generated objects (cut plane, halves,
    baked intermediates, previews, fixtures) so the scene is clean.

    Doesn't touch any objects you created yourself.
    """
    bl_idname = "quartermaster.reset_scene"
    bl_label  = "Reset Scene (clear QM)"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        prefixes = ("QM_", "_qm_", "_pin_")
        removed = 0
        for obj in list(bpy.data.objects):
            if obj.name.startswith(prefixes):
                bpy.data.objects.remove(obj, do_unlink=True)
                removed += 1
        self.report({"INFO"}, f"Removed {removed} Quartermaster object(s)")
        return {"FINISHED"}


CLASSES = (
    QM_OT_AddTestBlock,
    QM_OT_AddDovetailBlock,
    QM_OT_AddCutPlane,
    QM_OT_SnapCutPlane,
    QM_OT_PreviewJoint,
    QM_OT_ExecuteCut,
    QM_OT_ResetScene,
)
