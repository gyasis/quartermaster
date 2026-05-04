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


def cut_along_plane(
    target_obj,
    plane_empty,
    table_mm:      float = 0.0,
    tolerance_mm:  float = 0.0,
    override_spec: "JointSpec | None" = None,
    extra_meshes:  "list | None" = None,
) -> CutResult:
    """Bake `target_obj`'s modifier stack and split it into two halves using
    the joint type chosen by `pick_joint` (or `override_spec` if provided).
    Idempotent: removes prior `<name>_L` / `_R` / `_baked` outputs.

    Args:
      table_mm: > 0 upgrades a smooth scarf to a tabled (locked) variant; the
                value is the table width in mm. Has no effect on other joints.
      override_spec: bypass the picker entirely with a JointSpec the caller
                     constructed (e.g., to force tail_count > 1 dovetail).
      extra_meshes: meshes to boolean-UNION with target_obj before cutting.
                    Lets the operator handle assemblies (e.g., plate + bosses
                    as separate objects) by treating them as one solid.
    """
    import bpy
    from mathutils import Vector

    base_plane = cut_plane_from_empty(plane_empty)

    for suffix in ("_L", "_R", "_baked"):
        old = bpy.data.objects.get(target_obj.name + suffix)
        if old:
            bpy.data.objects.remove(old, do_unlink=True)

    baked = cuttable_copy(target_obj, name=f"{target_obj.name}_baked")
    if extra_meshes:
        for extra in extra_meshes:
            mod = baked.modifiers.new(name="qm_union", type="BOOLEAN")
            mod.object = extra
            mod.operation = "UNION"
            mod.solver = "EXACT"
            bpy.context.view_layer.objects.active = baked
            bpy.ops.object.modifier_apply(modifier=mod.name)

    corners = [baked.matrix_world @ Vector(c) for c in baked.bound_box]
    xs = [c.x for c in corners]; ys = [c.y for c in corners]; zs = [c.z for c in corners]
    bbox_min = (min(xs), min(ys), min(zs))
    bbox_max = (max(xs), max(ys), max(zs))
    thickness, seam_length = base_plane.measure(bbox_min, bbox_max)

    if override_spec is not None:
        spec = override_spec
    else:
        spec = pick_joint(thickness=thickness, seam_length=seam_length)

    if table_mm > 0 and spec.joint == JointType.SCARF:
        spec = JointSpec(
            joint=spec.joint,
            params={**spec.params, "table_mm": table_mm},
            pin_count=0,
            rationale=spec.rationale + f" | table {table_mm:.1f}mm",
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
        from ..joints.dovetail import dovetail_path_2d
        path = dovetail_path_2d(spec, thickness, seam_length)
        left, right = _cut_with_path(baked, base_plane, path, thickness, seam_length, target_obj.name, tolerance_mm)
    elif spec.joint == JointType.FINGER:
        from ..joints.finger import finger_path_2d
        path = finger_path_2d(spec, thickness, seam_length)
        left, right = _cut_with_path(baked, base_plane, path, thickness, seam_length, target_obj.name, tolerance_mm)
    elif spec.joint == JointType.BOX:
        from ..joints.box import box_path_2d
        path = box_path_2d(spec, thickness, seam_length)
        left, right = _cut_with_path(baked, base_plane, path, thickness, seam_length, target_obj.name, tolerance_mm)
    elif spec.joint == JointType.HALF_LAP:
        left, right = _cut_half_lap(baked, base_plane, spec, thickness, target_obj.name)
    elif spec.joint == JointType.SLIDING_DOVETAIL:
        left, right = _cut_sliding_dovetail(baked, base_plane, spec, thickness, target_obj.name, tolerance_mm)
    else:
        bpy.data.objects.remove(baked, do_unlink=True)
        raise NotImplementedError(
            f"Joint {spec.joint.value} not yet supported in the Blender pipeline"
        )

    target_obj.hide_set(True)
    baked.hide_set(True)
    if extra_meshes:
        for extra in extra_meshes:
            extra.hide_set(True)

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


def _cut_with_path(baked, base_plane, path, thickness, seam_length, target_name, tolerance_mm: float = 0.0):
    """Two-step path-based cut. Avoids non-convex cutter polygons (which
    confuse the EXACT boolean solver on multi-feature input meshes) by:

      1) Simple perpendicular cut with a big convex box covering +n half-space.
      2) For each "indentation" in the path (subsequence with n' > 0), build a
         convex prism for it and add to LEFT (UNION) / remove from RIGHT
         (DIFFERENCE). Each indentation is the trapezoid (dovetail) or
         rectangle (finger) of one tail/finger feature.

    `tolerance_mm` adds FDM clearance: the socket prism is expanded outward
    by this amount so the printed pieces slot together with `tolerance_mm`
    of clearance per side. Tail prism stays original size.

    Both steps use only convex shapes for booleans, which the solver handles
    reliably even on unioned multi-object inputs.
    """
    import bpy
    from mathutils import Vector

    n_axis = Vector(base_plane.normal).normalized()
    s_axis = Vector(base_plane.seam_axis).normalized()
    t_axis = n_axis.cross(s_axis).normalized()
    p0     = Vector(base_plane.point)

    corners       = [baked.matrix_world @ Vector(c) for c in baked.bound_box]
    pad           = 1.0
    n_max         = max((c - p0).dot(n_axis) for c in corners) + pad
    # Padded t-range for the cutting big-box (boolean robustness)
    t_min_padded  = min((c - p0).dot(t_axis) for c in corners) - pad
    t_max_padded  = max((c - p0).dot(t_axis) for c in corners) + pad
    # Unpadded t-range for the tail UNION step — UNION must not extend the
    # part past its actual surfaces.
    t_min_exact   = min((c - p0).dot(t_axis) for c in corners)
    t_max_exact   = max((c - p0).dot(t_axis) for c in corners)
    half_seam_pad = seam_length / 2 + pad

    # Step 1: perpendicular cut
    big_box_polygon = [
        (0.0,    -half_seam_pad),
        (n_max,  -half_seam_pad),
        (n_max,  +half_seam_pad),
        (0.0,    +half_seam_pad),
    ]
    big_box = _make_prism(big_box_polygon, base_plane, (t_min_padded, t_max_padded), name="_qm_big_box")

    def boolean_split(target, cutter, name, op):
        obj = target.copy()
        obj.data = target.data.copy()
        obj.name = name
        bpy.context.collection.objects.link(obj)
        mod = obj.modifiers.new(name="qm_cut", type="BOOLEAN")
        mod.object = cutter
        mod.operation = op
        mod.solver = "EXACT"
        bpy.context.view_layer.objects.active = obj
        bpy.ops.object.modifier_apply(modifier=mod.name)
        return obj

    left  = boolean_split(baked, big_box, target_name + "_L", "DIFFERENCE")
    right = boolean_split(baked, big_box, target_name + "_R", "INTERSECT")
    bpy.data.objects.remove(big_box, do_unlink=True)

    # Step 2: for each indentation (tail/finger), add to LEFT and subtract
    # from RIGHT. With tolerance_mm > 0, the socket prism (DIFFERENCE→RIGHT)
    # is offset outward so the printed parts have clearance per side.
    for idx, indent_polygon in enumerate(_path_indentations(path)):
        tail = _make_prism(indent_polygon, base_plane, (t_min_exact, t_max_exact), name=f"_qm_indent_{idx}")
        if tolerance_mm > 0:
            socket_polygon = _offset_polygon(indent_polygon, tolerance_mm)
            socket = _make_prism(socket_polygon, base_plane, (t_min_exact, t_max_exact), name=f"_qm_socket_{idx}")
        else:
            socket = tail

        for half, cutter, op in [(left, tail, "UNION"), (right, socket, "DIFFERENCE")]:
            mod = half.modifiers.new(name=f"qm_indent_{idx}", type="BOOLEAN")
            mod.object = cutter
            mod.operation = op
            mod.solver = "EXACT"
            bpy.context.view_layer.objects.active = half
            bpy.ops.object.modifier_apply(modifier=mod.name)

        bpy.data.objects.remove(tail, do_unlink=True)
        if socket is not tail:
            bpy.data.objects.remove(socket, do_unlink=True)

    return left, right


def _offset_polygon(polygon, distance):
    """Move each edge of a CCW polygon outward by `distance` (Minkowski-style).

    For a convex polygon, the result is the Minkowski sum with a disk of
    radius `distance`. Each vertex of the offset polygon lies at the
    intersection of its two adjacent offset edges; the formula moves the
    vertex along its outward bisector by `distance / cos(half-angle)`.

    Pure 2D math — testable without bpy. Polygon is given as a list of
    (x, y) tuples; CCW orientation expected (interior on the left of each
    edge).
    """
    import math

    if distance == 0:
        return list(polygon)
    n = len(polygon)
    if n < 3:
        return list(polygon)

    out = []
    for i in range(n):
        prev = polygon[(i - 1) % n]
        curr = polygon[i]
        nxt  = polygon[(i + 1) % n]

        e1x, e1y = curr[0] - prev[0], curr[1] - prev[1]
        e2x, e2y = nxt[0]  - curr[0], nxt[1]  - curr[1]
        l1 = math.hypot(e1x, e1y) or 1.0
        l2 = math.hypot(e2x, e2y) or 1.0
        e1x, e1y = e1x / l1, e1y / l1
        e2x, e2y = e2x / l2, e2y / l2

        # Outward normals (rotate edge 90 CW for a CCW polygon)
        n1x, n1y = e1y, -e1x
        n2x, n2y = e2y, -e2x

        bx, by = n1x + n2x, n1y + n2y
        bl = math.hypot(bx, by) or 1.0
        bx, by = bx / bl, by / bl

        cos_half = n1x * bx + n1y * by
        d_along  = distance / max(cos_half, 1e-6)

        out.append((curr[0] + bx * d_along, curr[1] + by * d_along))
    return out


def _path_indentations(path):
    """Yield convex polygons for each path subsequence with n' > 0.

    For a dovetail/finger path that runs from (0, -seam/2) to (0, +seam/2)
    with N tails, this yields N polygons — each is the tail's outline
    (anchor_before, ...bulge_points..., anchor_after) where anchor_* are the
    n=0 points immediately bracketing the bulge.
    """
    out = []
    i = 0
    n = len(path)
    while i < n:
        if path[i][0] > 0:
            start = i
            while i < n and path[i][0] > 0:
                i += 1
            before = path[start - 1] if start > 0       else (0.0, path[start][1])
            after  = path[i]         if i < n           else (0.0, path[i - 1][1])
            out.append([before, *path[start:i], after])
        else:
            i += 1
    return out


def _make_prism(polygon_2d, base_plane, t_range, name):
    """Extrude a 2D (n', s') polygon along the thickness axis between
    t_range = (t_min, t_max) to a 3D solid. Polygon must be simple (no
    self-intersections); convexity is recommended for boolean robustness."""
    import bpy, bmesh
    from mathutils import Vector

    n_axis = Vector(base_plane.normal).normalized()
    s_axis = Vector(base_plane.seam_axis).normalized()
    t_axis = n_axis.cross(s_axis).normalized()
    p0     = Vector(base_plane.point)
    t_min, t_max = t_range

    bm = bmesh.new()
    front_verts, back_verts = [], []
    for (np_, sp_) in polygon_2d:
        front_verts.append(bm.verts.new(p0 + n_axis * np_ + s_axis * sp_ + t_axis * t_min))
        back_verts.append(bm.verts.new(p0 + n_axis * np_ + s_axis * sp_ + t_axis * t_max))
    bm.verts.ensure_lookup_table()
    bm.faces.new(front_verts[::-1])
    bm.faces.new(back_verts)
    n = len(polygon_2d)
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


def _make_prism_seam(polygon_n_t, base_plane, s_range, name):
    """Extrude a 2D (n', t') polygon along the seam axis between s_range = (s_min, s_max).

    Mirror of `_make_prism` but with the polygon in the seam-cross-section
    plane instead of the seam-along plane. Used by half-lap and sliding
    dovetail, whose features run the full seam length.
    """
    import bpy, bmesh
    from mathutils import Vector

    n_axis = Vector(base_plane.normal).normalized()
    s_axis = Vector(base_plane.seam_axis).normalized()
    t_axis = n_axis.cross(s_axis).normalized()
    p0     = Vector(base_plane.point)
    s_min, s_max = s_range

    bm = bmesh.new()
    front_verts, back_verts = [], []
    for (np_, tp_) in polygon_n_t:
        front_verts.append(bm.verts.new(p0 + n_axis * np_ + s_axis * s_min + t_axis * tp_))
        back_verts.append(bm.verts.new(p0 + n_axis * np_ + s_axis * s_max + t_axis * tp_))
    bm.verts.ensure_lookup_table()
    bm.faces.new(front_verts[::-1])
    bm.faces.new(back_verts)
    n = len(polygon_n_t)
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


def _cut_sliding_dovetail(baked, base_plane, spec, thickness, target_name, tolerance_mm: float = 0.0):
    """Tenon (trapezoidal cross-section in n,t) on LEFT, matching groove on RIGHT.
    Tenon runs the full seam length. Pure convex prism — robust booleans."""
    import bpy
    from mathutils import Vector
    from ..joints.sliding_dovetail import sliding_dovetail_profile_2d

    n_axis = Vector(base_plane.normal).normalized()
    s_axis = Vector(base_plane.seam_axis).normalized()
    t_axis = n_axis.cross(s_axis).normalized()
    p0     = Vector(base_plane.point)

    corners       = [baked.matrix_world @ Vector(c) for c in baked.bound_box]
    pad           = 1.0
    n_max         = max((c - p0).dot(n_axis) for c in corners) + pad
    t_min_padded  = min((c - p0).dot(t_axis) for c in corners) - pad
    t_max_padded  = max((c - p0).dot(t_axis) for c in corners) + pad
    s_extents     = [(c - p0).dot(s_axis) for c in corners]
    s_min_exact, s_max_exact = min(s_extents), max(s_extents)
    s_min_padded, s_max_padded = s_min_exact - pad, s_max_exact + pad
    half_t_padded = max(abs(t_min_padded), abs(t_max_padded)) + pad

    # Step 1: perpendicular cut. Big-box covers +n half-space, full thickness, full seam.
    big_box = _make_prism(
        polygon_2d=[
            (0.0,    s_min_padded),
            (n_max,  s_min_padded),
            (n_max,  s_max_padded),
            (0.0,    s_max_padded),
        ],
        base_plane=base_plane,
        t_range=(t_min_padded, t_max_padded),
        name="_qm_big_box_sd",
    )

    def boolean_split(target, cutter, name, op):
        obj = target.copy()
        obj.data = target.data.copy()
        obj.name = name
        bpy.context.collection.objects.link(obj)
        mod = obj.modifiers.new(name="qm_cut", type="BOOLEAN")
        mod.object = cutter
        mod.operation = op
        mod.solver = "EXACT"
        bpy.context.view_layer.objects.active = obj
        bpy.ops.object.modifier_apply(modifier=mod.name)
        return obj

    left  = boolean_split(baked, big_box, target_name + "_L", "DIFFERENCE")
    right = boolean_split(baked, big_box, target_name + "_R", "INTERSECT")
    bpy.data.objects.remove(big_box, do_unlink=True)

    # Step 2: build tenon prism (and optional larger socket prism for tolerance)
    tenon_profile = sliding_dovetail_profile_2d(spec, thickness)
    tenon = _make_prism_seam(tenon_profile, base_plane, (s_min_exact, s_max_exact), name="_qm_tenon")
    if tolerance_mm > 0:
        socket_profile = _offset_polygon(tenon_profile, tolerance_mm)
        socket = _make_prism_seam(socket_profile, base_plane, (s_min_exact, s_max_exact), name="_qm_groove")
    else:
        socket = tenon

    for half, cutter, op in [(left, tenon, "UNION"), (right, socket, "DIFFERENCE")]:
        mod = half.modifiers.new(name="qm_sd", type="BOOLEAN")
        mod.object = cutter
        mod.operation = op
        mod.solver = "EXACT"
        bpy.context.view_layer.objects.active = half
        bpy.ops.object.modifier_apply(modifier=mod.name)

    bpy.data.objects.remove(tenon, do_unlink=True)
    if socket is not tenon:
        bpy.data.objects.remove(socket, do_unlink=True)

    return left, right


def _cut_half_lap(baked, base_plane, spec, thickness, target_name):
    """Half-lap: composes from two simple convex boxes via independent booleans.

      LEFT  = baked - top_box - bot_box
      RIGHT = (baked & top_box) UNION (baked & bot_box)

    Each cutter is a simple convex cube — no concave polygons or coincident
    faces to confuse the boolean solver.
    """
    import bpy, bmesh
    from mathutils import Vector
    from ..joints.half_lap import half_lap_path_2d

    path    = half_lap_path_2d(spec, thickness)
    overlap = abs(path[0][0])

    n_axis = Vector(base_plane.normal).normalized()
    s_axis = Vector(base_plane.seam_axis).normalized()
    t_axis = n_axis.cross(s_axis).normalized()
    p0     = Vector(base_plane.point)

    corners = [baked.matrix_world @ Vector(c) for c in baked.bound_box]
    pad     = 1.0
    n_max   = max((c - p0).dot(n_axis) for c in corners) + pad
    s_min   = min((c - p0).dot(s_axis) for c in corners) - pad
    s_max   = max((c - p0).dot(s_axis) for c in corners) + pad
    t_min   = min((c - p0).dot(t_axis) for c in corners) - pad
    t_max   = max((c - p0).dot(t_axis) for c in corners) + pad

    def make_simple_box(n_lo, n_hi, t_lo, t_hi, name):
        bm = bmesh.new()
        geom = bmesh.ops.create_cube(bm, size=1.0)
        n_size, s_size, t_size = n_hi - n_lo, s_max - s_min, t_hi - t_lo
        for v in geom["verts"]:
            n_p = n_lo  + (v.co.x + 0.5) * n_size
            s_p = s_min + (v.co.y + 0.5) * s_size
            t_p = t_lo  + (v.co.z + 0.5) * t_size
            v.co = p0 + n_axis * n_p + s_axis * s_p + t_axis * t_p
        mesh = bpy.data.meshes.new(f"{name}_mesh")
        bm.to_mesh(mesh)
        bm.free()
        obj = bpy.data.objects.new(name, mesh)
        bpy.context.collection.objects.link(obj)
        return obj

    # Each cutter extends very slightly past z=0 into the other's territory,
    # so the boolean step sweeps up any boundary faces left at z=0 by the
    # other cutter. Without this, a stray face from the previous DIFFERENCE
    # at z=0 lingers in the result.
    eps = 1e-3
    top_box = make_simple_box(-overlap, n_max, -eps,   t_max, "_qm_hl_top")
    bot_box = make_simple_box(+overlap, n_max, t_min,  +eps,  "_qm_hl_bot")

    def apply_bool(target, cutter, op):
        mod = target.modifiers.new(name="qm_cut", type="BOOLEAN")
        mod.object = cutter
        mod.operation = op
        mod.solver = "EXACT"
        bpy.context.view_layer.objects.active = target
        bpy.ops.object.modifier_apply(modifier=mod.name)
        # The EXACT solver can leave straggler verts/faces at coplanar
        # cutter boundaries — clean those up.
        bm = bmesh.new()
        bm.from_mesh(target.data)
        bmesh.ops.dissolve_degenerate(bm, dist=1e-4, edges=bm.edges[:])
        # Drop any verts left without face connections after dissolve
        loose_verts = [v for v in bm.verts if not v.link_faces]
        if loose_verts:
            bmesh.ops.delete(bm, geom=loose_verts, context="VERTS")
        bm.to_mesh(target.data)
        bm.free()

    # LEFT = baked - top_box - bot_box
    left = baked.copy()
    left.data = baked.data.copy()
    left.name = target_name + "_L"
    bpy.context.collection.objects.link(left)
    apply_bool(left, top_box, "DIFFERENCE")
    apply_bool(left, bot_box, "DIFFERENCE")

    # RIGHT = (baked & top_box) UNION (baked & bot_box)
    right_top = baked.copy()
    right_top.data = baked.data.copy()
    right_top.name = "_qm_right_top_tmp"
    bpy.context.collection.objects.link(right_top)
    apply_bool(right_top, top_box, "INTERSECT")

    right_bot = baked.copy()
    right_bot.data = baked.data.copy()
    right_bot.name = "_qm_right_bot_tmp"
    bpy.context.collection.objects.link(right_bot)
    apply_bool(right_bot, bot_box, "INTERSECT")

    # UNION the two halves
    apply_bool(right_top, right_bot, "UNION")
    right = right_top
    right.name = target_name + "_R"

    for tmp in (top_box, bot_box, right_bot):
        bpy.data.objects.remove(tmp, do_unlink=True)
    return left, right


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
