"""High-level cut pipeline: target object + cut-plane Empty -> two halves
with auto-picked joinery."""
from __future__ import annotations
from dataclasses import dataclass

from ..joint_strategy import JointSpec, JointType, pick_joint
from ..joints.scarf import scarf_plane, scarf_path_2d, pin_locations
from .adapter import cut_plane_from_empty, cuttable_copy


@dataclass
class CutResult:
    left:        object
    right:       object
    spec:        JointSpec
    thickness:   float
    seam_length: float


def cut_along_plane(target_obj, plane_empty, lockable: bool = False) -> CutResult:
    """Bake `target_obj`'s modifier stack and split it into two halves using
    the joint type chosen by `pick_joint`. Idempotent: removes prior
    `<name>_L` / `_R` / `_baked` outputs.

    Dispatches on `spec.joint`:
      - SCARF (smooth)   -> bisect plane + alignment pins
      - SCARF (tabled)   -> cutter mesh extruded along seam axis (lockable=True)
      - DOVETAIL         -> cutter mesh extruded along thickness axis

    `lockable=True` upgrades the smooth scarf to a tabled (locked) variant.
    Has no effect on dovetail (which already provides mechanical lock).
    """
    import bpy
    from mathutils import Vector

    base_plane = cut_plane_from_empty(plane_empty)

    for suffix in ("_L", "_R", "_baked"):
        old = bpy.data.objects.get(target_obj.name + suffix)
        if old:
            bpy.data.objects.remove(old, do_unlink=True)

    baked = cuttable_copy(target_obj, name=f"{target_obj.name}_baked")

    corners = [baked.matrix_world @ Vector(c) for c in baked.bound_box]
    xs = [c.x for c in corners]; ys = [c.y for c in corners]; zs = [c.z for c in corners]
    bbox_min = (min(xs), min(ys), min(zs))
    bbox_max = (max(xs), max(ys), max(zs))
    thickness, seam_length = base_plane.measure(bbox_min, bbox_max)

    spec = pick_joint(thickness=thickness, seam_length=seam_length)

    if lockable and spec.joint == JointType.SCARF:
        table_mm = max(thickness * 2.0, 6.0)
        spec = JointSpec(
            joint=spec.joint,
            params={**spec.params, "table_mm": table_mm},
            pin_count=0,
            rationale=spec.rationale + " | tabled lock",
        )

    if spec.joint == JointType.SCARF:
        if spec.params.get("table_mm", 0) > 0:
            left, right = _cut_tabled_scarf(baked, base_plane, spec, thickness, target_obj.name)
        else:
            left, right = _cut_smooth_scarf(baked, base_plane, spec, thickness, bbox_min, target_obj.name)
            pins = pin_locations(
                base_plane, spec,
                seam_origin=(base_plane.point[0], bbox_min[1], base_plane.point[2]),
                seam_length=seam_length,
                thickness=thickness,
            )
            for i, p in enumerate(pins):
                _drill_pin(p, left, right, i)
    elif spec.joint == JointType.DOVETAIL:
        left, right = _cut_dovetail(baked, base_plane, spec, thickness, seam_length, target_obj.name)
    else:
        bpy.data.objects.remove(baked, do_unlink=True)
        raise NotImplementedError(
            f"Joint {spec.joint.value} not yet supported in the Blender pipeline"
        )

    target_obj.hide_set(True)
    baked.hide_set(True)

    return CutResult(
        left=left, right=right, spec=spec,
        thickness=thickness, seam_length=seam_length,
    )


# Backwards-compat alias from before the dispatcher refactor.
cut_with_scarf = cut_along_plane


def _cut_smooth_scarf(baked, base_plane, spec, thickness, bbox_min, target_name):
    import bpy, bmesh
    from mathutils import Vector

    sp = scarf_plane(base_plane, spec, thickness=thickness)

    def cut_half(name, clear_outer):
        obj = baked.copy()
        obj.data = baked.data.copy()
        obj.name = name
        bpy.context.collection.objects.link(obj)
        bm = bmesh.new()
        bm.from_mesh(obj.data)
        bmesh.ops.bisect_plane(
            bm,
            geom=bm.verts[:] + bm.edges[:] + bm.faces[:],
            plane_co=Vector(sp.point),
            plane_no=Vector(sp.normal),
            clear_outer=clear_outer,
            clear_inner=not clear_outer,
        )
        boundary = [e for e in bm.edges if e.is_boundary]
        if boundary:
            bmesh.ops.holes_fill(bm, edges=boundary)
        bm.to_mesh(obj.data)
        bm.free()
        return obj

    return cut_half(target_name + "_L", True), cut_half(target_name + "_R", False)


def _cut_tabled_scarf(baked, base_plane, spec, thickness, target_name):
    """Build a cutter solid from the Z-shape path, then boolean DIFFERENCE for
    LEFT half and INTERSECT (with the plate) for RIGHT half."""
    import bpy
    cutter = _build_scarf_cutter(baked, base_plane, spec, thickness, name="_qm_scarf_cutter")

    def boolean_half(name, op):
        obj = baked.copy()
        obj.data = baked.data.copy()
        obj.name = name
        bpy.context.collection.objects.link(obj)
        mod = obj.modifiers.new(name="qm_cut", type="BOOLEAN")
        mod.object = cutter
        mod.operation = op
        mod.solver = "EXACT"
        bpy.context.view_layer.objects.active = obj
        bpy.ops.object.modifier_apply(modifier=mod.name)
        return obj

    left  = boolean_half(target_name + "_L", "DIFFERENCE")
    right = boolean_half(target_name + "_R", "INTERSECT")
    bpy.data.objects.remove(cutter, do_unlink=True)
    return left, right


def _build_scarf_cutter(plate_obj, base_plane, spec, thickness, name):
    """Build a 3D cutter solid. The cutter occupies the +normal half-space
    relative to the cut path, extruded along the seam axis. Designed for
    plates that are roughly aligned with the cut plane's local frame."""
    import bpy, bmesh
    from mathutils import Vector

    path = scarf_path_2d(spec, thickness)
    half_t = thickness / 2

    n_axis = Vector(base_plane.normal).normalized()
    s_axis = Vector(base_plane.seam_axis).normalized()
    t_axis = n_axis.cross(s_axis).normalized()
    p0     = Vector(base_plane.point)

    corners = [plate_obj.matrix_world @ Vector(c) for c in plate_obj.bound_box]
    n_extents = [(c - p0).dot(n_axis) for c in corners]
    s_extents = [(c - p0).dot(s_axis) for c in corners]
    pad_n = pad_s = pad_t = 1.0
    n_max = max(n_extents) + pad_n
    s_min = min(s_extents) - pad_s
    s_max = max(s_extents) + pad_s

    # 2D profile in (n', t'), CCW when viewed in +seam direction:
    profile = [(path[0][0], half_t + pad_t)]   # top-left of cutter (above cut start)
    profile.extend(path)                       # the cut path
    profile.append((n_max, path[-1][1]))       # right of bottom
    profile.append((n_max, half_t + pad_t))    # top-right

    bm = bmesh.new()
    front_verts = []
    back_verts  = []
    for (np_, tp_) in profile:
        front_verts.append(bm.verts.new(p0 + n_axis * np_ + t_axis * tp_ + s_axis * s_min))
        back_verts.append(bm.verts.new(p0 + n_axis * np_ + t_axis * tp_ + s_axis * s_max))
    bm.verts.ensure_lookup_table()

    bm.faces.new(front_verts[::-1])  # front cap (-seam side)
    bm.faces.new(back_verts)         # back cap (+seam side)
    n = len(profile)
    for i in range(n):
        j = (i + 1) % n
        bm.faces.new([front_verts[i], back_verts[i], back_verts[j], front_verts[j]])
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)

    mesh = bpy.data.meshes.new(f"{name}_mesh")
    bm.to_mesh(mesh)
    bm.free()
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.collection.objects.link(obj)
    return obj


def _cut_dovetail(baked, base_plane, spec, thickness, seam_length, target_name):
    """Build a cutter solid from the dovetail path and boolean DIFFERENCE for
    LEFT half (which gets the tail) and INTERSECT (with the plate) for RIGHT
    (which gets the matching socket)."""
    import bpy
    cutter = _build_dovetail_cutter(
        baked, base_plane, spec, thickness, seam_length, name="_qm_dovetail_cutter",
    )

    def boolean_half(name, op):
        obj = baked.copy()
        obj.data = baked.data.copy()
        obj.name = name
        bpy.context.collection.objects.link(obj)
        mod = obj.modifiers.new(name="qm_cut", type="BOOLEAN")
        mod.object = cutter
        mod.operation = op
        mod.solver = "EXACT"
        bpy.context.view_layer.objects.active = obj
        bpy.ops.object.modifier_apply(modifier=mod.name)
        return obj

    left  = boolean_half(target_name + "_L", "DIFFERENCE")
    right = boolean_half(target_name + "_R", "INTERSECT")
    bpy.data.objects.remove(cutter, do_unlink=True)
    return left, right


def _build_dovetail_cutter(plate_obj, base_plane, spec, thickness, seam_length, name):
    """3D cutter for dovetails: 2D path in (n', s'), extruded along thickness.

    Different extrusion axis from tabled scarf — scarf path lives in the
    (normal, thickness) plane and extrudes along seam; dovetail path lives in
    the (normal, seam) plane and extrudes along thickness.
    """
    import bpy, bmesh
    from mathutils import Vector
    from ..joints.dovetail import dovetail_path_2d

    path = dovetail_path_2d(spec, thickness, seam_length)
    half_t    = thickness / 2
    half_seam = seam_length / 2
    pad_n = pad_t = 1.0

    n_axis = Vector(base_plane.normal).normalized()
    s_axis = Vector(base_plane.seam_axis).normalized()
    t_axis = n_axis.cross(s_axis).normalized()
    p0     = Vector(base_plane.point)

    corners   = [plate_obj.matrix_world @ Vector(c) for c in plate_obj.bound_box]
    n_max     = max((c - p0).dot(n_axis) for c in corners) + pad_n

    polygon = list(path) + [
        (n_max, +half_seam),
        (n_max, -half_seam),
    ]

    bm = bmesh.new()
    front_verts, back_verts = [], []
    for (np_, sp_) in polygon:
        front_verts.append(bm.verts.new(p0 + n_axis * np_ + s_axis * sp_ + t_axis * (-half_t - pad_t)))
        back_verts.append(bm.verts.new(p0 + n_axis * np_ + s_axis * sp_ + t_axis * (+half_t + pad_t)))
    bm.verts.ensure_lookup_table()

    bm.faces.new(front_verts[::-1])
    bm.faces.new(back_verts)
    n = len(polygon)
    for i in range(n):
        j = (i + 1) % n
        bm.faces.new([front_verts[i], back_verts[i], back_verts[j], front_verts[j]])
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)

    mesh = bpy.data.meshes.new(f"{name}_mesh")
    bm.to_mesh(mesh)
    bm.free()
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.collection.objects.link(obj)
    return obj


def _drill_pin(pin, left, right, idx):
    import bpy
    from mathutils import Vector

    bpy.ops.object.select_all(action='DESELECT')
    bpy.ops.mesh.primitive_cylinder_add(radius=pin.diameter / 2, depth=pin.length, location=pin.center)
    cyl = bpy.context.active_object
    cyl.name = f"_pin_cutter_{idx}"
    cyl.rotation_mode = "QUATERNION"
    cyl.rotation_quaternion = Vector((0, 0, 1)).rotation_difference(Vector(pin.axis))

    for half in (left, right):
        mod = half.modifiers.new(name=f"pin_{idx}", type='BOOLEAN')
        mod.object = cyl
        mod.operation = 'DIFFERENCE'
        bpy.context.view_layer.objects.active = half
        bpy.ops.object.modifier_apply(modifier=mod.name)

    bpy.data.objects.remove(cyl, do_unlink=True)
