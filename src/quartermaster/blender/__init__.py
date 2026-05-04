"""Quartermaster — auto-split prints that exceed your build plate.

This package is both:
  - A regular Python module (import the adapter functions for scripting).
  - A Blender add-on (call register() to install operators + N-panel).
"""

bl_info = {
    "name":        "Quartermaster",
    "author":      "Quartermaster",
    "version":     (0, 0, 1),
    "blender":     (4, 0, 0),
    "location":    "View3D > N > Quartermaster",
    "description": "Auto-split oversized prints with the right joinery for the stock",
    "category":    "Mesh",
}

from .adapter import (
    cut_plane_from_empty,
    cut_plane_from_matrix,
    cuttable_copy,
    add_cut_plane_helper,
    QM_CUT_PLANE_PROP,
)

__all__ = [
    "cut_plane_from_empty",
    "cut_plane_from_matrix",
    "cuttable_copy",
    "add_cut_plane_helper",
    "QM_CUT_PLANE_PROP",
    "register",
    "unregister",
]


def register():
    """Install operators + N-panel into the running Blender session."""
    import bpy
    from . import operators, panel

    bpy.types.Scene.qm_use_table_lock = bpy.props.BoolProperty(
        name="Locked (tabled) joint",
        description="Add a perpendicular step at mid-thickness for grip + alignment",
        default=False,
    )

    for cls in (*operators.CLASSES, *panel.CLASSES):
        try:
            bpy.utils.unregister_class(cls)
        except (RuntimeError, ValueError):
            pass
        bpy.utils.register_class(cls)


def unregister():
    import bpy
    from . import operators, panel

    for cls in (*panel.CLASSES, *operators.CLASSES):
        try:
            bpy.utils.unregister_class(cls)
        except (RuntimeError, ValueError):
            pass

    if hasattr(bpy.types.Scene, "qm_use_table_lock"):
        del bpy.types.Scene.qm_use_table_lock
