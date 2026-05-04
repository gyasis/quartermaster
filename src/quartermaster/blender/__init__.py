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


_SCENE_PROPS = (
    "qm_joint_override",
    "qm_tail_count",
    "qm_dovetail_angle",
    "qm_table_mm",
    "qm_tolerance_mm",
    # Older boolean kept for migration only — drop after a release
    "qm_use_table_lock",
)


def register():
    """Install operators + N-panel into the running Blender session."""
    import bpy
    from . import operators, panel

    bpy.types.Scene.qm_joint_override = bpy.props.EnumProperty(
        name="Joint",
        description="Force a joint type, or AUTO to use the picker",
        items=[
            ("AUTO",     "Auto (picker)", "Use the picker's automatic choice"),
            ("DOVETAIL", "Dovetail",      "Force a dovetail (trapezoidal flare)"),
        ],
        default="AUTO",
    )
    bpy.types.Scene.qm_tail_count = bpy.props.IntProperty(
        name="Tails",
        description="Number of dovetail tails along the seam (only used when Joint = Dovetail)",
        default=1, min=1, max=10,
    )
    bpy.types.Scene.qm_dovetail_angle = bpy.props.FloatProperty(
        name="Dovetail angle (deg)",
        description="Flare angle of the tail; 7-10 deg is the FDM sweet spot",
        default=10.0, min=2.0, max=20.0,
    )
    bpy.types.Scene.qm_table_mm = bpy.props.FloatProperty(
        name="Lock step (mm)",
        description="Tabled scarf step width at mid-thickness (0 = smooth scarf, no mechanical lock)",
        default=0.0, min=0.0, max=50.0, soft_max=20.0, subtype="DISTANCE",
    )
    bpy.types.Scene.qm_tolerance_mm = bpy.props.FloatProperty(
        name="Print clearance (mm)",
        description="Per-side clearance between tail and socket — needed for FDM (typical 0.1-0.2)",
        default=0.15, min=0.0, max=2.0, soft_max=0.5, subtype="DISTANCE",
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

    for prop in _SCENE_PROPS:
        if hasattr(bpy.types.Scene, prop):
            delattr(bpy.types.Scene, prop)
