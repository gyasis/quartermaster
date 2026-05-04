"""Test fixtures for Quartermaster — clean, known-dimensions geometry to
exercise the add-on without the edge cases of CAD-imported meshes.

Calling code can use create_test_block to drop a parametric cuboid into the
scene; expected cut results are then computable from the inputs alone, which
makes the in-Blender smoke test deterministic.
"""
from __future__ import annotations
from typing import Tuple


def create_test_block(
    name:     str = "QM_TestBlock",
    size:     Tuple[float, float, float] = (300.0, 200.0, 4.0),
    location: Tuple[float, float, float] = (0.0, 0.0, 0.0),
):
    """Create or replace a parametric cuboid named `name`.

    The resulting mesh is axis-aligned, centered at `location`, with NO
    modifiers — making it the cleanest possible target for the cut pipeline.
    Default 300x200x4mm sits in the 3-5mm thickness bucket with a 200mm
    medium-length seam, which is what the picker is most thoroughly tested
    against.
    """
    import bpy

    # Replace if already present so the operator is idempotent
    old = bpy.data.objects.get(name)
    if old:
        bpy.data.objects.remove(old, do_unlink=True)

    bpy.ops.mesh.primitive_cube_add(size=1.0, location=location)
    obj = bpy.context.active_object
    obj.name = name
    obj.scale = size
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    return obj
