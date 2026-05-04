"""Blender-side integration smoke test for Quartermaster.

Exercises every operator and asserts on the geometry it produces. Runnable two
ways:

  1. From inside Blender (or via the MCP):
        exec(open("scripts/blender_smoke.py").read())

  2. Headless:
        blender --background --python scripts/blender_smoke.py

Exits with non-zero status on failure so CI can pick up the result.
"""
import math
import sys
from pathlib import Path

# Make src/ importable when run from the project root.
# Fall back to a hardcoded path when __file__ is unavailable (interactive exec).
try:
    HERE = Path(__file__).resolve().parent
    QM_SRC = HERE.parent / "src"
except NameError:
    QM_SRC = Path("/Users/gyasisutton/Documents/code/quartermaster/src")
if str(QM_SRC) not in sys.path:
    sys.path.insert(0, str(QM_SRC))

import bpy  # noqa: E402
from mathutils import Vector  # noqa: E402

# Always reload — picks up source edits during dev
for mod_name in [m for m in list(sys.modules) if m.startswith("quartermaster")]:
    del sys.modules[mod_name]

import quartermaster.blender as qm_blender  # noqa: E402
from quartermaster import pick_joint, JointType  # noqa: E402

qm_blender.register()


# --- helpers -----------------------------------------------------------------

failures: list[str] = []


def check(condition: bool, msg: str) -> None:
    if condition:
        print(f"  ok   {msg}")
    else:
        failures.append(msg)
        print(f"  FAIL {msg}")


def world_bbox_x(obj):
    verts = [obj.matrix_world @ v.co for v in obj.data.vertices]
    xs = [v.x for v in verts]
    return min(xs), max(xs)


def world_z_range(obj):
    verts = [obj.matrix_world @ v.co for v in obj.data.vertices]
    zs = [v.z for v in verts]
    return min(zs), max(zs)


def cleanup():
    """Remove anything Quartermaster created so each test starts clean."""
    for obj in list(bpy.data.objects):
        if obj.name.startswith(("QM_", "_qm_", "_pin_")):
            bpy.data.objects.remove(obj, do_unlink=True)


# --- tests -------------------------------------------------------------------

def test_add_test_block():
    print("\n[1] Add Test Block")
    cleanup()
    bpy.ops.quartermaster.add_test_block()
    check("QM_TestBlock" in bpy.data.objects, "test block exists")
    block = bpy.data.objects["QM_TestBlock"]
    check(len(block.data.vertices) == 8, f"clean cube has 8 verts (got {len(block.data.vertices)})")
    check(block.dimensions[0] == 300.0, f"X = 300 (got {block.dimensions[0]})")
    check(block.dimensions[1] == 200.0, f"Y = 200 (got {block.dimensions[1]})")
    check(block.dimensions[2] == 4.0,   f"Z = 4 (got {block.dimensions[2]})")
    check(len(block.modifiers) == 0, "no modifiers (raw mesh == evaluated mesh)")


def test_add_cut_plane():
    print("\n[2] Add Cut Plane")
    bpy.ops.quartermaster.add_cut_plane()
    check("QM_CutPlane" in bpy.data.objects, "cut plane Empty exists")
    empty = bpy.data.objects["QM_CutPlane"]
    check(empty.empty_display_type == "ARROWS", "empty type is ARROWS")
    check(empty.get("qm_cut_plane") is True, "tagged with qm_cut_plane property")


def test_picker_unit_agrees_with_runtime():
    print("\n[3] Picker output matches unit-test prediction")
    spec = pick_joint(thickness=4.0, seam_length=200.0)
    check(spec.joint == JointType.SCARF, f"joint == SCARF (got {spec.joint.value})")
    check(spec.params["overlap_mm"] == 32.0, f"overlap_mm == 32 (got {spec.params['overlap_mm']})")
    check(spec.params["ratio"] == 8, f"ratio == 8 (got {spec.params['ratio']})")
    check(spec.pin_count == 2, f"pin_count == 2 (got {spec.pin_count})")


def test_smooth_scarf_cut():
    print("\n[4] Smooth scarf cut")
    # Orient the cut plane: local +Z = world +X (perpendicular YZ cut)
    empty = bpy.data.objects["QM_CutPlane"]
    empty.rotation_mode = "XYZ"
    empty.rotation_euler = (0.0, math.pi / 2, 0.0)
    bpy.context.view_layer.update()

    block = bpy.data.objects["QM_TestBlock"]
    bpy.ops.object.select_all(action="DESELECT")
    block.select_set(True)
    bpy.context.view_layer.objects.active = block
    bpy.ops.quartermaster.execute_cut()

    check("QM_TestBlock_L" in bpy.data.objects, "left half created")
    check("QM_TestBlock_R" in bpy.data.objects, "right half created")
    left = bpy.data.objects["QM_TestBlock_L"]
    right = bpy.data.objects["QM_TestBlock_R"]

    l_min, l_max = world_bbox_x(left)
    r_min, r_max = world_bbox_x(right)
    check(abs(l_min - (-150)) < 0.1, f"left bbox X min ~ -150 (got {l_min:.2f})")
    check(abs(l_max -   16 ) < 0.1, f"left bbox X max ~ +16 (got {l_max:.2f})")
    check(abs(r_min - (-16)) < 0.1, f"right bbox X min ~ -16 (got {r_min:.2f})")
    check(abs(r_max -  150 ) < 0.1, f"right bbox X max ~ +150 (got {r_max:.2f})")

    z_min, z_max = world_z_range(left)
    check(abs(z_min - (-2)) < 0.01 and abs(z_max - 2) < 0.01,
          f"left has full Z thickness 0..4mm  (got {z_min:.2f}..{z_max:.2f})")
    check(len(left.data.vertices) > 8,
          f"left has pin-hole geometry ({len(left.data.vertices)} verts > 8)")


def test_tabled_scarf_cut():
    print("\n[5] Tabled (locked) scarf cut")
    cleanup()
    bpy.ops.quartermaster.add_test_block()
    bpy.ops.quartermaster.add_cut_plane()
    empty = bpy.data.objects["QM_CutPlane"]
    empty.rotation_mode = "XYZ"
    empty.rotation_euler = (0.0, math.pi / 2, 0.0)
    bpy.context.view_layer.update()

    bpy.context.scene.qm_table_mm = 8.0  # explicit lock-step width via slider
    block = bpy.data.objects["QM_TestBlock"]
    bpy.ops.object.select_all(action="DESELECT")
    block.select_set(True)
    bpy.context.view_layer.objects.active = block
    bpy.ops.quartermaster.execute_cut()

    left  = bpy.data.objects["QM_TestBlock_L"]
    right = bpy.data.objects["QM_TestBlock_R"]

    # Same bbox extents as smooth (overlap region is the same)
    l_min, l_max = world_bbox_x(left)
    r_min, r_max = world_bbox_x(right)
    check(abs(l_min - (-150)) < 0.1, f"tabled left bbox X min ~ -150 (got {l_min:.2f})")
    check(abs(l_max -   16 ) < 0.1, f"tabled left bbox X max ~ +16 (got {l_max:.2f})")
    check(abs(r_min - (-16)) < 0.1, f"tabled right bbox X min ~ -16 (got {r_min:.2f})")
    check(abs(r_max -  150 ) < 0.1, f"tabled right bbox X max ~ +150 (got {r_max:.2f})")

    # 12 verts each — clean Z-step profile, no pin-hole geometry
    check(len(left.data.vertices) == 12, f"tabled left = 12 verts (got {len(left.data.vertices)})")
    check(len(right.data.vertices) == 12, f"tabled right = 12 verts (got {len(right.data.vertices)})")

    # The table sits at z=0; expect a vertex at the inner table edge in each half
    left_table_xs = sorted({round(v.co.x, 2) for v in left.data.vertices if abs(v.co.z) < 0.01})
    check(any(abs(x - (-4.0)) < 0.1 for x in left_table_xs),
          f"left has mid-thickness vert at x=-4 (table inner edge): xs={left_table_xs}")

    right_table_xs = sorted({round(v.co.x, 2) for v in right.data.vertices if abs(v.co.z) < 0.01})
    check(any(abs(x - (+4.0)) < 0.1 for x in right_table_xs),
          f"right has mid-thickness vert at x=+4 (table inner edge): xs={right_table_xs}")


def test_idempotent_recut():
    """Re-running the cut on the same source should clean up prior outputs.

    NB: this only holds when the *source* is active. If the user re-runs while
    a half is active, that's a different operation (cutting the half). The
    add-on may want to detect that and redirect — see TODO in operators.py.
    """
    print("\n[6] Re-cutting cleans up prior outputs")
    block = bpy.data.objects["QM_TestBlock"]
    block.hide_set(False)
    bpy.ops.object.select_all(action="DESELECT")
    block.select_set(True)
    bpy.context.view_layer.objects.active = block

    n_before = sum(1 for o in bpy.data.objects if o.name.startswith("QM_TestBlock_"))
    bpy.ops.quartermaster.execute_cut()
    n_after = sum(1 for o in bpy.data.objects if o.name.startswith("QM_TestBlock_"))
    check(n_before == n_after, f"object count unchanged after re-cut ({n_before} -> {n_after})")


# --- run ---------------------------------------------------------------------

def test_dovetail_cut():
    print("\n[7] Dovetail cut on dovetail block")
    cleanup()
    bpy.ops.quartermaster.add_dovetail_block()
    bpy.ops.quartermaster.add_cut_plane()
    empty = bpy.data.objects["QM_CutPlane"]
    empty.rotation_mode = "XYZ"
    empty.rotation_euler = (0.0, math.pi / 2, 0.0)
    bpy.context.view_layer.update()

    bpy.context.scene.qm_table_mm = 0.0
    bpy.context.scene.qm_joint_override = "AUTO"
    block = bpy.data.objects["QM_DovetailBlock"]
    bpy.ops.object.select_all(action="DESELECT")
    block.select_set(True)
    bpy.context.view_layer.objects.active = block
    bpy.ops.quartermaster.execute_cut()

    check("QM_DovetailBlock_L" in bpy.data.objects, "left half created")
    check("QM_DovetailBlock_R" in bpy.data.objects, "right half created")
    left  = bpy.data.objects["QM_DovetailBlock_L"]
    right = bpy.data.objects["QM_DovetailBlock_R"]

    # 6mm thick, 60mm seam: picker -> DOVETAIL angle=10, tail=1
    # protrusion = max(1.5*6, 8) = 9 mm
    l_min, l_max = world_bbox_x(left)
    r_min, r_max = world_bbox_x(right)
    check(abs(l_min - (-40)) < 0.1, f"left X min ~ -40 plate edge (got {l_min:.2f})")
    check(abs(l_max -    9) < 0.5, f"left X max ~ +9 (tail outer end) (got {l_max:.2f})")
    check(abs(r_min -    0) < 0.5, f"right X min ~ 0 (cut line) (got {r_min:.2f})")
    check(abs(r_max -   40) < 0.1, f"right X max ~ +40 plate edge (got {r_max:.2f})")

    # Both halves are real solids
    z_min, z_max = world_z_range(left)
    check(abs(z_max - z_min - 6.0) < 0.01, f"left Z thickness ~ 6mm (got {z_max - z_min:.2f})")


def test_active_half_redirects_to_source():
    print("\n[8] Active-half redirect (regression check)")
    cleanup()
    bpy.ops.quartermaster.add_test_block()
    bpy.ops.quartermaster.add_cut_plane()
    empty = bpy.data.objects["QM_CutPlane"]
    empty.rotation_mode = "XYZ"
    empty.rotation_euler = (0.0, math.pi / 2, 0.0)
    bpy.context.view_layer.update()

    bpy.context.scene.qm_table_mm = 0.0
    bpy.context.scene.qm_joint_override = "AUTO"
    block = bpy.data.objects["QM_TestBlock"]
    bpy.ops.object.select_all(action="DESELECT")
    block.select_set(True)
    bpy.context.view_layer.objects.active = block
    bpy.ops.quartermaster.execute_cut()

    # Now activate the LEFT half (the kind of thing a user does after a cut)
    # and re-cut. The operator should redirect to the source, NOT cascade.
    left = bpy.data.objects["QM_TestBlock_L"]
    bpy.ops.object.select_all(action="DESELECT")
    left.select_set(True)
    bpy.context.view_layer.objects.active = left
    bpy.ops.quartermaster.execute_cut()

    check("QM_TestBlock_L_L" not in bpy.data.objects, "no cascade — QM_TestBlock_L_L not created")
    check("QM_TestBlock_L_R" not in bpy.data.objects, "no cascade — QM_TestBlock_L_R not created")
    check("QM_TestBlock_L"   in bpy.data.objects,    "fresh QM_TestBlock_L still exists (re-cut from source)")


def test_multi_tail_dovetail_via_override():
    print("\n[9] Multi-tail dovetail (override_spec, tail_count=2)")
    cleanup()
    bpy.ops.quartermaster.add_test_block()  # 300x200x4mm — picker would say SCARF
    bpy.ops.quartermaster.add_cut_plane()
    empty = bpy.data.objects["QM_CutPlane"]
    empty.rotation_mode = "XYZ"
    empty.rotation_euler = (0.0, math.pi / 2, 0.0)
    bpy.context.view_layer.update()

    # Force a 2-tail dovetail via override_spec (bypasses the picker)
    from quartermaster import JointSpec, JointType
    from quartermaster.blender.cut import cut_along_plane

    block = bpy.data.objects["QM_TestBlock"]
    spec = JointSpec(
        JointType.DOVETAIL,
        {"angle_deg": 10, "tail_count": 2},
        pin_count=0,
        rationale="smoke: forced multi-tail",
    )
    cut_along_plane(block, empty, override_spec=spec)

    check("QM_TestBlock_L" in bpy.data.objects, "left half created")
    left = bpy.data.objects["QM_TestBlock_L"]

    # 4mm thick, 200mm seam, 2 tails:
    #   protrusion = max(1.5*4, 8) = 8mm
    #   base_width = 4*4 = 16mm  ;  flare = 8 * tan(10°) = 1.41
    #   top_width = 18.82mm
    #   gap = (200 - 32) / 3 = 56mm
    #   tail centers: -36, +36
    l_min, l_max = world_bbox_x(left)
    check(abs(l_min - (-150)) < 0.1, f"left X min ~ -150 (got {l_min:.2f})")
    check(abs(l_max -    8) < 0.5,  f"left X max ~ +8 (tail outer end) (got {l_max:.2f})")

    # Both tails should appear: vertices at x=8 (the tail outer face) on TWO
    # disjoint Y bands — one near -36, one near +36.
    tail_outer_ys = sorted(
        round(v.co.y, 2)
        for v in left.data.vertices
        if abs((left.matrix_world @ v.co).x - 8) < 0.5
    )
    print(f"  tail-outer-corner Y values on left half: {tail_outer_ys}")
    has_negative_band = any(y < -20 for y in tail_outer_ys)
    has_positive_band = any(y >  20 for y in tail_outer_ys)
    check(has_negative_band, f"tail at negative Y band: {tail_outer_ys}")
    check(has_positive_band, f"tail at positive Y band: {tail_outer_ys}")
    check(len(tail_outer_ys) >= 4,
          f"both tails have outer corners (>= 4 verts at x=8): got {len(tail_outer_ys)}")


def test_finger_cut_via_picker():
    print("\n[10] Finger joint (via picker on long-seam block)")
    cleanup()
    # 400x150x4mm block: thickness=4 (3-5mm), seam=150 (medium-ish)... actually picker picks SCARF for medium.
    # Need long_seam (> 300). Use 400x150x4 with cut along Y -> seam = 150 = medium.
    # Use 500x100x4 with cut along Y -> seam = 100mm, picker = SCARF medium too.
    # Force a long seam: use a 400-long block and cut perpendicular to its short axis.
    # 200x400x4 with cut along Y axis = seam_length=400 (long_seam) → picker = FINGER.
    from quartermaster.blender.fixtures import create_test_block
    block = create_test_block(name="QM_FingerBlock", size=(200.0, 400.0, 4.0), location=(0.0, 0.0, 0.0))

    bpy.ops.quartermaster.add_cut_plane()
    empty = bpy.data.objects["QM_CutPlane"]
    empty.rotation_mode = "XYZ"
    empty.rotation_euler = (0.0, math.pi / 2, 0.0)  # cut perpendicular to X (seam runs along Y, length 400)
    bpy.context.view_layer.update()

    bpy.context.scene.qm_table_mm = 0.0
    bpy.context.scene.qm_joint_override = "AUTO"
    bpy.ops.object.select_all(action="DESELECT")
    block.select_set(True)
    bpy.context.view_layer.objects.active = block
    bpy.ops.quartermaster.execute_cut()

    check("QM_FingerBlock_L" in bpy.data.objects, "left half created")
    check("QM_FingerBlock_R" in bpy.data.objects, "right half created")
    left = bpy.data.objects["QM_FingerBlock_L"]
    # Picker for thickness=4, seam=400 -> FINGER pitch=12 depth=6.4
    # n_fingers = 400/12 = 33; outer-corner X = +6.4
    l_xs_at_outer = sorted({
        round((left.matrix_world @ v.co).y, 1)
        for v in left.data.vertices
        if abs((left.matrix_world @ v.co).x - 6.4) < 0.5
    })
    print(f"  finger-outer Y values (should be many, alternating): {len(l_xs_at_outer)} unique")
    check(len(l_xs_at_outer) >= 20, f"many fingers visible (>= 20 outer Y-values, got {len(l_xs_at_outer)})")


def test_snap_to_longest_axis():
    print("\n[11] Snap to longest axis")
    cleanup()
    # 300x100x4 — longest axis is X
    from quartermaster.blender.fixtures import create_test_block
    block = create_test_block(name="QM_SnapBlock", size=(300.0, 100.0, 4.0), location=(50.0, 30.0, 0.0))
    bpy.ops.quartermaster.add_cut_plane()
    bpy.ops.object.select_all(action="DESELECT")
    block.select_set(True)
    bpy.context.view_layer.objects.active = block

    bpy.ops.quartermaster.snap_cut_plane()
    plane = bpy.data.objects["QM_CutPlane"]
    bpy.context.view_layer.update()

    # The plane should be at the block's center
    check(abs(plane.location.x - 50) < 0.01, f"plane.x = block center.x = 50 (got {plane.location.x:.2f})")
    check(abs(plane.location.y - 30) < 0.01, f"plane.y = block center.y = 30 (got {plane.location.y:.2f})")

    # Plane's local +Z should point along world +X (the longest axis)
    z_world = plane.matrix_world.to_3x3() @ Vector((0, 0, 1))
    check(abs(z_world.x - 1.0) < 0.01, f"plane local +Z aligned with world +X (got x={z_world.x:.3f})")
    check(abs(z_world.y) < 0.01,       f"plane local +Z has no Y component (got y={z_world.y:.3f})")
    check(abs(z_world.z) < 0.01,       f"plane local +Z has no Z component (got z={z_world.z:.3f})")


def test_dovetail_via_panel_override():
    """The Joint dropdown should produce the same result as override_spec=..."""
    print("\n[12] Joint override via panel property")
    cleanup()
    bpy.ops.quartermaster.add_test_block()
    bpy.ops.quartermaster.add_cut_plane()
    empty = bpy.data.objects["QM_CutPlane"]
    empty.rotation_mode = "XYZ"
    empty.rotation_euler = (0.0, math.pi / 2, 0.0)
    bpy.context.view_layer.update()

    bpy.context.scene.qm_joint_override = "DOVETAIL"
    bpy.context.scene.qm_tail_count = 3
    bpy.context.scene.qm_dovetail_angle = 10.0
    bpy.context.scene.qm_table_mm = 0.0

    block = bpy.data.objects["QM_TestBlock"]
    bpy.ops.object.select_all(action="DESELECT")
    block.select_set(True)
    bpy.context.view_layer.objects.active = block
    bpy.ops.quartermaster.execute_cut()

    left = bpy.data.objects["QM_TestBlock_L"]
    # 3 tails with default base_width=4*4=16, gap = (200 - 48)/4 = 38
    # tail outer corners at x=8 (protrusion) — count distinct Y values
    outer_ys = sorted({
        round((left.matrix_world @ v.co).y, 1)
        for v in left.data.vertices
        if abs((left.matrix_world @ v.co).x - 8) < 0.5
    })
    print(f"  outer-corner Ys: {outer_ys}")
    # 3 tails -> 6 outer corner Y positions (each tail has 2)
    check(len(outer_ys) >= 6, f"3 tails -> >= 6 outer-corner Ys (got {len(outer_ys)}: {outer_ys})")

    # Reset for subsequent tests
    bpy.context.scene.qm_joint_override = "AUTO"
    bpy.context.scene.qm_tail_count = 1


def test_multi_object_union():
    print("\n[13] Multi-object union before cut")
    cleanup()
    # Plate + flange extension (both 4mm thick, in-plane only). Vertical
    # asymmetric assemblies (e.g., plate + tall boss) are not yet supported
    # cleanly by the joint cutter — see TODO in cut.py. This test verifies
    # the UNION step itself: extras are baked into the cut input so the right
    # half includes geometry from the flange that wasn't part of the plate.
    from quartermaster.blender.fixtures import create_test_block
    plate  = create_test_block(name="QM_UnionPlate",  size=(300.0, 200.0, 4.0), location=(0.0, 0.0, 0.0))
    flange = create_test_block(name="QM_UnionFlange", size=( 40.0,  40.0, 4.0), location=(170.0, 0.0, 0.0))

    # Activate plate so the cut plane lands at plate center (origin),
    # not at flange center.
    bpy.context.view_layer.objects.active = plate
    bpy.ops.quartermaster.add_cut_plane()
    empty = bpy.data.objects["QM_CutPlane"]
    empty.rotation_mode = "XYZ"
    empty.rotation_euler = (0.0, math.pi / 2, 0.0)
    empty.location = (0.0, 0.0, 0.0)
    bpy.context.view_layer.update()

    # Both 4mm — picker would say SCARF; pin the joint so the test is deterministic
    bpy.context.scene.qm_joint_override = "DOVETAIL"
    bpy.context.scene.qm_tail_count = 1
    bpy.context.scene.qm_dovetail_angle = 10.0
    bpy.context.scene.qm_table_mm = 0.0

    bpy.ops.object.select_all(action="DESELECT")
    flange.select_set(True)
    plate.select_set(True)
    bpy.context.view_layer.objects.active = plate
    bpy.ops.quartermaster.execute_cut()

    check("QM_UnionPlate_L" in bpy.data.objects, "left half created")
    check("QM_UnionPlate_R" in bpy.data.objects, "right half created")
    right = bpy.data.objects["QM_UnionPlate_R"]
    x_max = max((right.matrix_world @ v.co).x for v in right.data.vertices)
    # Plate alone ends at x=+150; the flange extends to x=+190. If the union
    # actually fed into the cut, the right half's bbox X-max will be ~190.
    check(x_max > 180, f"right half includes the flange past plate end (got x_max={x_max:.2f}, want > 180)")


def _reset_scene_props():
    """Restore panel state to defaults so tests don't leak settings into each other."""
    bpy.context.scene.qm_joint_override = "AUTO"
    bpy.context.scene.qm_tail_count     = 1
    bpy.context.scene.qm_dovetail_angle = 10.0
    bpy.context.scene.qm_table_mm       = 0.0
    bpy.context.scene.qm_tolerance_mm   = 0.0
    bpy.context.scene.qm_overlap_mm     = 10.0


def test_tolerance_expands_socket():
    """Tolerance expands the socket prism in (n', s'); the tail prism stays
    original size. Look at the socket's INNER far edge position on the right
    half — without tolerance it's at n'=protrusion=9; with tolerance=0.5 it
    moves to n'=9.5 (the socket is bigger so the printed pieces have clearance).
    """
    print("\n[14] FDM tolerance: socket bigger than tail")
    cleanup()
    bpy.ops.quartermaster.add_dovetail_block()  # 80x60x6, single dovetail, protrusion=9
    bpy.ops.quartermaster.add_cut_plane()
    empty = bpy.data.objects["QM_CutPlane"]
    empty.rotation_mode = "XYZ"
    empty.rotation_euler = (0.0, math.pi / 2, 0.0)
    bpy.context.view_layer.update()

    # Baseline: tolerance=0 → socket inner edge at x=9
    bpy.context.scene.qm_tolerance_mm = 0.0
    bpy.context.scene.qm_joint_override = "AUTO"
    block = bpy.data.objects["QM_DovetailBlock"]
    bpy.ops.object.select_all(action="DESELECT")
    block.select_set(True)
    bpy.context.view_layer.objects.active = block
    bpy.ops.quartermaster.execute_cut()
    right_tight = bpy.data.objects["QM_DovetailBlock_R"]
    xs_tight = sorted({round((right_tight.matrix_world @ v.co).x, 2) for v in right_tight.data.vertices})
    check(9.0 in xs_tight, f"baseline: right has socket inner edge at x=9.0 (got xs={xs_tight})")

    # Tolerance=0.5: socket inner edge moves to x=9.5
    bpy.context.scene.qm_tolerance_mm = 0.5
    block.hide_set(False)
    bpy.ops.object.select_all(action="DESELECT")
    block.select_set(True)
    bpy.context.view_layer.objects.active = block
    bpy.ops.quartermaster.execute_cut()
    right_loose = bpy.data.objects["QM_DovetailBlock_R"]
    xs_loose = sorted({round((right_loose.matrix_world @ v.co).x, 2) for v in right_loose.data.vertices})
    check(9.5 in xs_loose, f"with tolerance: right has socket inner edge at x=9.5 (got xs={xs_loose})")
    check(9.0 not in xs_loose, "socket inner edge moved (no x=9.0 anymore)")

    # Tail UNCHANGED — left's tail still extends to x=9.0
    left_loose = bpy.data.objects["QM_DovetailBlock_L"]
    l_max = max((left_loose.matrix_world @ v.co).x for v in left_loose.data.vertices)
    check(abs(l_max - 9.0) < 0.05, f"tail outer end unchanged (got {l_max:.3f}, want 9.0)")


def test_half_lap_via_override():
    print("\n[15] Half-lap via panel override")
    cleanup()
    from quartermaster.blender.fixtures import create_test_block
    block = create_test_block(name="QM_HalfLapBlock", size=(120.0, 60.0, 6.0), location=(0.0, 0.0, 0.0))
    bpy.ops.quartermaster.add_cut_plane()
    empty = bpy.data.objects["QM_CutPlane"]
    empty.rotation_mode = "XYZ"
    empty.rotation_euler = (0.0, math.pi / 2, 0.0)
    bpy.context.view_layer.update()

    bpy.context.scene.qm_joint_override = "HALF_LAP"
    bpy.context.scene.qm_overlap_mm     = 10.0
    bpy.ops.object.select_all(action="DESELECT")
    block.select_set(True)
    bpy.context.view_layer.objects.active = block
    bpy.ops.quartermaster.execute_cut()

    check("QM_HalfLapBlock_L" in bpy.data.objects, "left half created")
    check("QM_HalfLapBlock_R" in bpy.data.objects, "right half created")
    left  = bpy.data.objects["QM_HalfLapBlock_L"]
    right = bpy.data.objects["QM_HalfLapBlock_R"]

    # Half-lap geometry:
    #   LEFT  = full at n<-overlap, BOTTOM half (z<0) at n in [-overlap, +overlap]
    #   RIGHT = full at n>+overlap, TOP    half (z>0) at n in [-overlap, +overlap]
    # bbox X-max for LEFT: +10 (where the bottom-half lap ends)
    l_max = max((left.matrix_world @ v.co).x for v in left.data.vertices)
    check(abs(l_max - 10.0) < 0.5, f"left bbox X max ~ +10 (bottom-lap end) (got {l_max:.2f})")
    # bbox X-min for RIGHT: -10 (where the top-half lap starts)
    r_min = min((right.matrix_world @ v.co).x for v in right.data.vertices)
    check(abs(r_min - (-10.0)) < 0.5, f"right bbox X min ~ -10 (top-lap start) (got {r_min:.2f})")

    # LEFT's TOP face (z=+3) only exists for n < -overlap (no top material in the lap)
    l_top_xs = sorted({round((left.matrix_world @ v.co).x, 2)
                       for v in left.data.vertices
                       if abs((left.matrix_world @ v.co).z - (+3.0)) < 0.1})
    check(max(l_top_xs) <= -10.0 + 0.5,
          f"left's top face ends at x=-10 (no top material in the lap): xs={l_top_xs}")


def test_sliding_dovetail_via_picker():
    print("\n[16] Sliding dovetail (picker chooses for thick + long seam)")
    cleanup()
    from quartermaster.blender.fixtures import create_test_block
    # 12mm thick, 200mm seam → picker returns SLIDING_DOVETAIL
    block = create_test_block(name="QM_SlidingBlock", size=(160.0, 200.0, 12.0), location=(0.0, 0.0, 0.0))
    bpy.ops.quartermaster.add_cut_plane()
    empty = bpy.data.objects["QM_CutPlane"]
    empty.rotation_mode = "XYZ"
    empty.rotation_euler = (0.0, math.pi / 2, 0.0)
    bpy.context.view_layer.update()

    bpy.context.scene.qm_joint_override = "AUTO"
    bpy.ops.object.select_all(action="DESELECT")
    block.select_set(True)
    bpy.context.view_layer.objects.active = block
    bpy.ops.quartermaster.execute_cut()

    check("QM_SlidingBlock_L" in bpy.data.objects, "left half created")
    check("QM_SlidingBlock_R" in bpy.data.objects, "right half created")
    left  = bpy.data.objects["QM_SlidingBlock_L"]
    right = bpy.data.objects["QM_SlidingBlock_R"]

    # 12mm thick → picker depth_mm = 12*0.6 = 7.2; angle=12, base_width = max(12*0.5, 6) = 6
    # → flare = 7.2*tan(12°) = 1.53; top_width = 9.06; half_top = 4.53
    # LEFT tenon tip at n = +depth = +7.2.
    l_max = max((left.matrix_world @ v.co).x for v in left.data.vertices)
    check(abs(l_max - 7.2) < 0.5, f"left tenon tip ~ +7.2 (picker depth) (got {l_max:.2f})")

    # The flare in t-direction at the tip — top_width=9.06, so half_top ≈ 4.53.
    tenon_tip_zs = sorted({round((left.matrix_world @ v.co).z, 2)
                           for v in left.data.vertices
                           if abs((left.matrix_world @ v.co).x - 7.2) < 0.5})
    check(len(tenon_tip_zs) >= 2, f"tenon tip has corner verts in z (got {tenon_tip_zs})")
    if tenon_tip_zs:
        check(max(tenon_tip_zs) > 4.0, f"tenon flares wider in z at the tip (max z={max(tenon_tip_zs):.2f} > 4)")
        check(min(tenon_tip_zs) < -4.0, f"tenon flares wider in z at the tip (min z={min(tenon_tip_zs):.2f} < -4)")


def test_half_lap_on_asymmetric_assembly():
    """Half-lap's bbox-based cutter is the right choice on asymmetric inputs:
    we WANT the cut to slice through the full thickness of any protrusion so
    the boss ends up in RIGHT and not in LEFT. This test pins that behavior.
    """
    print("\n[A1] Half-lap on plate + tall boss")
    cleanup()
    from quartermaster.blender.fixtures import create_test_block
    plate = create_test_block(name="QM_HLAsym",     size=(300.0, 200.0, 4.0),  location=(0.0, 0.0, 0.0))
    boss  = create_test_block(name="QM_HLAsymBoss", size=( 40.0,  40.0, 12.0), location=(80.0, 0.0, 6.0))

    bpy.context.view_layer.objects.active = plate
    bpy.ops.quartermaster.add_cut_plane()
    empty = bpy.data.objects["QM_CutPlane"]
    empty.rotation_mode = "XYZ"
    empty.rotation_euler = (0.0, math.pi / 2, 0.0)
    empty.location = (0.0, 0.0, 0.0)
    bpy.context.view_layer.update()

    bpy.context.scene.qm_joint_override = "HALF_LAP"
    bpy.context.scene.qm_overlap_mm = 10.0
    bpy.context.scene.qm_table_mm = 0.0

    bpy.ops.object.select_all(action="DESELECT")
    boss.select_set(True)
    plate.select_set(True)
    bpy.context.view_layer.objects.active = plate
    bpy.ops.quartermaster.execute_cut()

    check("QM_HLAsym_L" in bpy.data.objects, "left half created")
    check("QM_HLAsym_R" in bpy.data.objects, "right half created")
    left, right = bpy.data.objects["QM_HLAsym_L"], bpy.data.objects["QM_HLAsym_R"]

    # RIGHT should include the boss (full z=12)
    r_z_max = max((right.matrix_world @ v.co).z for v in right.data.vertices)
    check(r_z_max > 11, f"right contains boss (z_max={r_z_max:.2f})")

    # LEFT should stay at plate thickness only (no boss material)
    l_z_max = max((left.matrix_world @ v.co).z for v in left.data.vertices)
    check(l_z_max <= 2.5, f"left stays within plate (z_max={l_z_max:.2f}, want ≤ 2.5)")

    # LEFT's bbox X max = +10 (lap end on bottom half)
    l_x_max = max((left.matrix_world @ v.co).x for v in left.data.vertices)
    check(abs(l_x_max - 10.0) < 0.5, f"left bottom-lap ends at x=10 (got {l_x_max:.2f})")


def test_sliding_dovetail_on_asymmetric_assembly():
    """Picker now measures local thickness, so sliding-dovetail is sized to the
    plate at the cut and the tenon doesn't extend LEFT into a phantom pillar.
    """
    print("\n[A2] Sliding dovetail on plate + boss (override)")
    cleanup()
    from quartermaster.blender.fixtures import create_test_block
    # Plate 12mm thick (so SLIDING_DOVETAIL geometry actually fits) + tall boss
    plate = create_test_block(name="QM_SDAsym",     size=(300.0, 200.0, 12.0), location=(0.0, 0.0, 0.0))
    boss  = create_test_block(name="QM_SDAsymBoss", size=( 40.0,  40.0,  8.0), location=(80.0, 0.0, 10.0))
    # boss z-center 10, height 8 -> z=6..14. Plate z=-6..6. Combined z=-6..14.

    bpy.context.view_layer.objects.active = plate
    bpy.ops.quartermaster.add_cut_plane()
    empty = bpy.data.objects["QM_CutPlane"]
    empty.rotation_mode = "XYZ"
    empty.rotation_euler = (0.0, math.pi / 2, 0.0)
    empty.location = (0.0, 0.0, 0.0)
    bpy.context.view_layer.update()

    bpy.context.scene.qm_joint_override = "SLIDING_DOVETAIL"
    bpy.context.scene.qm_dovetail_angle = 12.0

    bpy.ops.object.select_all(action="DESELECT")
    boss.select_set(True)
    plate.select_set(True)
    bpy.context.view_layer.objects.active = plate
    bpy.ops.quartermaster.execute_cut()

    check("QM_SDAsym_L" in bpy.data.objects, "left half created")
    left, right = bpy.data.objects["QM_SDAsym_L"], bpy.data.objects["QM_SDAsym_R"]

    # Override doesn't set depth_mm so the generator default takes over:
    # max(12*0.6, 8) = 8. The point of this test is the local-thickness
    # *behaviour*, not the exact dim — without per-region thickness the bbox
    # would have been ~20mm and produced a much larger tenon.
    l_max = max((left.matrix_world @ v.co).x for v in left.data.vertices)
    check(abs(l_max - 8.0) < 0.5, f"tenon tip at x=+8 (got {l_max:.2f})")

    # LEFT's z extent stays within plate (z=-6..6) — no phantom material above
    l_z_max = max((left.matrix_world @ v.co).z for v in left.data.vertices)
    check(l_z_max <= 6.5, f"left stays within plate (z_max={l_z_max:.2f}, want ≤ 6.5)")

    # RIGHT contains boss
    r_z_max = max((right.matrix_world @ v.co).z for v in right.data.vertices)
    check(r_z_max > 13, f"right contains boss (z_max={r_z_max:.2f})")


def test_per_region_thickness_asymmetric_assembly():
    print("\n[A] Asymmetric assembly: thickness measured at cut, not bbox")
    cleanup()
    from quartermaster.blender.fixtures import create_test_block
    # Plate (4mm) + tall boss (12mm) sitting on top, far from the cut.
    # bbox thickness = 14mm (would route picker to SLIDING_DOVETAIL with
    # gigantic tenon); cross-section at x=0 sees only the plate -> 4mm,
    # which routes to scarf 8:1 — the right joint for the local stock.
    plate = create_test_block(name="QM_AsymmPlate", size=(300.0, 200.0, 4.0), location=(0.0, 0.0, 0.0))
    boss  = create_test_block(name="QM_AsymmBoss",  size=(40.0, 40.0, 12.0), location=(80.0, 0.0, 6.0))

    # Cut plane at origin so the bisect intersects the plate (not the boss)
    bpy.context.view_layer.objects.active = plate
    bpy.ops.quartermaster.add_cut_plane()
    empty = bpy.data.objects["QM_CutPlane"]
    empty.rotation_mode = "XYZ"
    empty.rotation_euler = (0.0, math.pi / 2, 0.0)
    empty.location = (0.0, 0.0, 0.0)
    bpy.context.view_layer.update()

    # Force DOVETAIL so we exercise the path cutter on an asymmetric input.
    bpy.context.scene.qm_joint_override = "DOVETAIL"
    bpy.context.scene.qm_tail_count = 1
    bpy.context.scene.qm_dovetail_angle = 10.0
    bpy.context.scene.qm_table_mm = 0.0
    bpy.context.scene.qm_tolerance_mm = 0.0

    bpy.ops.object.select_all(action="DESELECT")
    boss.select_set(True)
    plate.select_set(True)
    bpy.context.view_layer.objects.active = plate
    bpy.ops.quartermaster.execute_cut()

    check("QM_AsymmPlate_L" in bpy.data.objects, "left half created")
    check("QM_AsymmPlate_R" in bpy.data.objects, "right half created")

    right = bpy.data.objects["QM_AsymmPlate_R"]
    r_z_max = max((right.matrix_world @ v.co).z for v in right.data.vertices)
    check(r_z_max > 5, f"right half includes the boss above plate top (got z_max={r_z_max:.2f})")

    # The critical check: LEFT must NOT extend in z past the plate.
    # With bbox-thickness, the dovetail tail prism would reach z=12 (boss top)
    # and UNION-extend LEFT into a 14mm-tall pillar at the tail location.
    # With cross-section thickness, tail stays in plate's z range.
    left = bpy.data.objects["QM_AsymmPlate_L"]
    l_z_max = max((left.matrix_world @ v.co).z for v in left.data.vertices)
    check(l_z_max <= 2.5, f"left half stays at plate thickness (got z_max={l_z_max:.2f}, want ≤ 2.5)")


def test_box_via_picker():
    print("\n[17] Box joint (picker chooses for thick + short seam)")
    cleanup()
    from quartermaster.blender.fixtures import create_test_block
    # 12mm thick, 60mm seam -> picker returns BOX
    block = create_test_block(name="QM_BoxBlock", size=(80.0, 60.0, 12.0), location=(0.0, 0.0, 0.0))
    bpy.ops.quartermaster.add_cut_plane()
    empty = bpy.data.objects["QM_CutPlane"]
    empty.rotation_mode = "XYZ"
    empty.rotation_euler = (0.0, math.pi / 2, 0.0)
    bpy.context.view_layer.update()

    bpy.context.scene.qm_joint_override = "AUTO"
    bpy.context.scene.qm_tolerance_mm = 0.0
    bpy.ops.object.select_all(action="DESELECT")
    block.select_set(True)
    bpy.context.view_layer.objects.active = block
    bpy.ops.quartermaster.execute_cut()

    check("QM_BoxBlock_L" in bpy.data.objects, "left half created")
    check("QM_BoxBlock_R" in bpy.data.objects, "right half created")
    left = bpy.data.objects["QM_BoxBlock_L"]

    # 3 fingers default, depth=thickness=12 → finger tips at x=12
    l_max = max((left.matrix_world @ v.co).x for v in left.data.vertices)
    check(abs(l_max - 12.0) < 0.5, f"left box-finger tip at x=+12 (got {l_max:.2f})")

    # finger_width = seam_length / (2*N+1) = 60/7 ≈ 8.57
    # 3 fingers, alternating with 4 gaps. Verts at x=12 should appear at 6 distinct Y positions.
    finger_outer_ys = sorted({round((left.matrix_world @ v.co).y, 2)
                              for v in left.data.vertices
                              if abs((left.matrix_world @ v.co).x - 12.0) < 0.5})
    check(len(finger_outer_ys) == 6, f"3 fingers -> 6 outer-corner Ys (got {len(finger_outer_ys)}: {finger_outer_ys})")


def test_preview_creates_wireframe():
    print("\n[17] Joint preview creates wireframe object")
    cleanup()
    bpy.ops.quartermaster.add_test_block()
    bpy.ops.quartermaster.add_cut_plane()
    empty = bpy.data.objects["QM_CutPlane"]
    empty.rotation_mode = "XYZ"
    empty.rotation_euler = (0.0, math.pi / 2, 0.0)
    bpy.context.view_layer.update()

    block = bpy.data.objects["QM_TestBlock"]
    bpy.ops.object.select_all(action="DESELECT")
    block.select_set(True)
    bpy.context.view_layer.objects.active = block

    # AUTO -> picker chooses scarf for 4mm/200mm
    bpy.ops.quartermaster.preview_joint()
    check("QM_JointPreview" in bpy.data.objects, "preview object created")
    preview = bpy.data.objects["QM_JointPreview"]
    check(len(preview.data.edges) >= 1, f"preview has edges (got {len(preview.data.edges)})")
    check(len(preview.data.polygons) == 0, "preview is wireframe-only (no faces)")

    # Switch to dovetail and re-preview — should replace, not stack
    bpy.context.scene.qm_joint_override = "DOVETAIL"
    bpy.context.scene.qm_tail_count = 2
    bpy.ops.quartermaster.preview_joint()
    preview = bpy.data.objects["QM_JointPreview"]
    # 2-tail dovetail path: 4*2+2 = 10 points -> 9 segments (edges)
    check(len(preview.data.edges) == 9, f"2-tail preview has 9 edges (got {len(preview.data.edges)})")


def test_reset_scene_clears_qm_objects():
    print("\n[18] Reset Scene removes QM_-prefixed objects")
    # Set up some QM stuff
    bpy.ops.quartermaster.add_test_block()
    bpy.ops.quartermaster.add_cut_plane()
    qm_count_before = sum(1 for o in bpy.data.objects if o.name.startswith("QM_"))
    check(qm_count_before > 0, f"QM objects exist before reset (got {qm_count_before})")

    # Add a non-QM object that should survive
    from quartermaster.blender.fixtures import create_test_block
    keep = create_test_block(name="KeepMe", size=(50, 50, 5), location=(200, 0, 0))

    bpy.ops.quartermaster.reset_scene()
    qm_count_after = sum(1 for o in bpy.data.objects if o.name.startswith("QM_"))
    check(qm_count_after == 0, f"all QM objects cleared (got {qm_count_after})")
    check("KeepMe" in bpy.data.objects, "non-QM objects preserved")
    bpy.data.objects.remove(bpy.data.objects["KeepMe"], do_unlink=True)


def main():
    tests = [
        test_add_test_block,
        test_add_cut_plane,
        test_picker_unit_agrees_with_runtime,
        test_smooth_scarf_cut,
        test_tabled_scarf_cut,
        test_idempotent_recut,
        test_dovetail_cut,
        test_active_half_redirects_to_source,
        test_multi_tail_dovetail_via_override,
        test_finger_cut_via_picker,
        test_snap_to_longest_axis,
        test_dovetail_via_panel_override,
        test_multi_object_union,
        test_tolerance_expands_socket,
        test_half_lap_via_override,
        test_sliding_dovetail_via_picker,
        test_box_via_picker,
        test_per_region_thickness_asymmetric_assembly,
        test_half_lap_on_asymmetric_assembly,
        test_sliding_dovetail_on_asymmetric_assembly,
        test_preview_creates_wireframe,
        test_reset_scene_clears_qm_objects,
    ]
    for t in tests:
        _reset_scene_props()
        try:
            t()
        except Exception as exc:
            failures.append(f"{t.__name__}: raised {type(exc).__name__}: {exc}")
            print(f"  FAIL (raised) {exc}")

    print("\n" + "=" * 50)
    if failures:
        print(f"FAILED: {len(failures)} check(s)")
        for f in failures:
            print(f"  - {f}")
    else:
        print("ALL CHECKS PASSED")
    return len(failures)


# Always run on import / exec — whether invoked as `__main__` (headless), via
# exec() in an interactive session, or imported. Headless mode signals the
# OS so CI can pick up the result.
_qm_failure_count = main()
if bpy.app.background and _qm_failure_count:
    sys.exit(1)
