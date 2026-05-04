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
    bpy.context.scene.qm_use_table_lock = False

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

    bpy.context.scene.qm_use_table_lock = True
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

    bpy.context.scene.qm_use_table_lock = False
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

    bpy.context.scene.qm_use_table_lock = False
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


def main():
    test_add_test_block()
    test_add_cut_plane()
    test_picker_unit_agrees_with_runtime()
    test_smooth_scarf_cut()
    test_tabled_scarf_cut()
    test_idempotent_recut()
    test_dovetail_cut()
    test_active_half_redirects_to_source()

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
