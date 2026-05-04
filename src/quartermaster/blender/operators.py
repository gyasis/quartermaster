"""Blender operators exposing Quartermaster actions to the user."""
from __future__ import annotations
import bpy

from .adapter import add_cut_plane_helper, QM_CUT_PLANE_PROP
from .cut import cut_with_scarf
from .fixtures import create_test_block


def _find_cut_plane():
    return next((o for o in bpy.data.objects if o.get(QM_CUT_PLANE_PROP)), None)


class QM_OT_AddCutPlane(bpy.types.Operator):
    """Drop a draggable cut-plane Empty into the scene. Local +Z is the cut \
normal; local +Y is the seam direction."""
    bl_idname = "quartermaster.add_cut_plane"
    bl_label = "Add Cut Plane"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        location = tuple(context.scene.cursor.location)
        if context.active_object and context.active_object.type == "MESH":
            # Default to the active mesh's center for convenience
            ob = context.active_object
            corners = [ob.matrix_world @ v for v in (
                __import__("mathutils").Vector(c) for c in ob.bound_box
            )]
            cx = sum(c.x for c in corners) / 8
            cy = sum(c.y for c in corners) / 8
            cz = sum(c.z for c in corners) / 8
            location = (cx, cy, cz)

        empty = add_cut_plane_helper(name="QM_CutPlane", location=location, size=120.0)
        bpy.ops.object.select_all(action="DESELECT")
        empty.select_set(True)
        context.view_layer.objects.active = empty

        # Activate the unified Transform tool so the move/rotate/scale gizmo
        # arrows appear directly on the empty — no need to remember G/R hotkeys.
        try:
            bpy.ops.wm.tool_set_by_id(name="builtin.transform")
        except (RuntimeError, TypeError):
            pass
        # Also force-show object transform gizmos in any active 3D viewport
        for area in context.screen.areas:
            if area.type == "VIEW_3D":
                for space in area.spaces:
                    if space.type == "VIEW_3D":
                        space.show_gizmo = True
                        space.show_gizmo_object_translate = True
                        space.show_gizmo_object_rotate = True

        self.report({"INFO"}, f"Added {empty.name} — drag the gizmo arrows to position")
        return {"FINISHED"}


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
        try:
            result = cut_with_scarf(
                target, plane,
                lockable=getattr(context.scene, "qm_use_table_lock", False),
            )
        except Exception as exc:
            self.report({"ERROR"}, f"Cut failed: {exc}")
            return {"CANCELLED"}
        table = result.spec.params.get("table_mm", 0)
        variant = f" + table {table:.0f}mm lock" if table else ""
        self.report(
            {"INFO"},
            f"{result.spec.joint.value.upper()}{variant}: t={result.thickness:.1f}mm "
            f"seam={result.seam_length:.0f}mm pins={result.spec.pin_count}",
        )
        return {"FINISHED"}


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
        self.report(
            {"INFO"},
            f"Added {block.name} (300x200x4mm) — picker target: scarf 8:1, 32mm overlap, 2 pins",
        )
        return {"FINISHED"}


CLASSES = (QM_OT_AddTestBlock, QM_OT_AddCutPlane, QM_OT_ExecuteCut)
