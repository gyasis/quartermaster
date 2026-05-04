"""Adapter between Blender objects and Quartermaster core.

Responsibilities:
- Convert a user-placed Empty into a CutPlane (the cut-plane-helper UX).
- Bake modifier stacks into a cuttable mesh copy. Without this, bisecting a
  Solidify/Boolean/Bevel-modified object operates on the *raw* mesh (often a
  flat 2D quad), not the visible 3D form. This is a structural concern: any
  Quartermaster cutter must consume the evaluated mesh.
"""
from __future__ import annotations
from typing import Any

from ..plane import CutPlane

# Custom property tag attached to plane-helper Empties so the plugin can find
# them in a scene without relying on names.
QM_CUT_PLANE_PROP = "qm_cut_plane"


def cut_plane_from_matrix(matrix_world: Any) -> CutPlane:
    """Construct a CutPlane from a 4x4 world matrix.

    Convention:
      local +Z -> cut normal (the direction halves separate)
      local +Y -> seam axis (the long direction of the cut)
    Local +X is implicit (the thickness axis); it falls out of normal x seam.

    `matrix_world` is duck-typed: anything with a `.translation` and a `.col`
    iterable that exposes 4-vectors works (Blender mathutils.Matrix qualifies).
    """
    t = matrix_world.translation
    point = (float(t.x), float(t.y), float(t.z))
    rot = matrix_world.to_3x3()
    seam_axis = rot.col[1]
    normal    = rot.col[2]
    return CutPlane(
        point=point,
        normal=(float(normal[0]),    float(normal[1]),    float(normal[2])),
        seam_axis=(float(seam_axis[0]), float(seam_axis[1]), float(seam_axis[2])),
    )


def cut_plane_from_empty(empty) -> CutPlane:
    """Read a Blender Empty's transform and produce a CutPlane.

    Caller is expected to have already validated the object is the right kind
    of helper (e.g., empty.get(QM_CUT_PLANE_PROP) is True).
    """
    return cut_plane_from_matrix(empty.matrix_world)


def cuttable_copy(obj, name: str):
    """Return a new Blender object whose mesh is the evaluated form of `obj`.

    All modifiers on `obj` are baked into the new mesh. The new object's
    world transform matches the source so its mesh sits where it was visually.

    Without this step, downstream bmesh ops cut whatever the *raw* mesh data
    is, which for many CAD-imported objects is just a few control verts under
    a Solidify/Boolean modifier — and the cut produces a flat artifact instead
    of slicing the visible 3D solid.
    """
    import bpy  # imported lazily so the rest of the package tests bpy-free

    deps = bpy.context.evaluated_depsgraph_get()
    ev = obj.evaluated_get(deps)
    mesh = bpy.data.meshes.new_from_object(ev)
    mesh.name = f"{name}_mesh"
    new_obj = bpy.data.objects.new(name, mesh)
    new_obj.matrix_world = obj.matrix_world.copy()
    bpy.context.collection.objects.link(new_obj)
    return new_obj


def add_cut_plane_helper(name: str = "QM_CutPlane", location=(0.0, 0.0, 0.0), size: float = 50.0):
    """Create a plane-helper Empty in the active scene.

    The user moves/rotates this Empty in the viewport to position the cut.
    The Empty is tagged with QM_CUT_PLANE_PROP so the plugin can find it.
    """
    import bpy

    empty = bpy.data.objects.new(name, None)
    empty.empty_display_type = "ARROWS"
    empty.empty_display_size = size
    empty.location = location
    empty[QM_CUT_PLANE_PROP] = True
    bpy.context.collection.objects.link(empty)
    return empty
