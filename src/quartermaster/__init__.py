"""Quartermaster — auto-split prints that exceed your build plate.

This package is also a Blender add-on entry point. When the user installs
the zip via Edit > Preferences > Add-ons > Install..., Blender imports this
__init__.py, reads `bl_info`, and calls `register()`. The actual operators
and N-panel live under `quartermaster.blender`; this module just delegates.

For pytest the bl_info dict is harmless and the register() function isn't
called, so the bpy import inside `.blender` never happens.
"""

bl_info = {
    "name":        "Quartermaster",
    "author":      "Gyasi Sutton",
    "version":     (0, 0, 1),
    "blender":     (4, 0, 0),
    "location":    "View3D > N > Quartermaster",
    "description": "Auto-split oversized prints with the right joinery for the stock thickness",
    "category":    "Mesh",
    "doc_url":     "https://github.com/gyasis/quartermaster",
    "tracker_url": "https://github.com/gyasis/quartermaster/issues",
}

from .joint_strategy import JointType, JointSpec, pick_joint, viable_joints
from .plane          import CutPlane

__all__ = [
    "JointType", "JointSpec", "pick_joint", "viable_joints", "CutPlane",
    "register", "unregister",
]


def register():
    """Blender add-on entry point — installs operators and the N-panel."""
    from .blender import register as _register
    _register()


def unregister():
    from .blender import unregister as _unregister
    _unregister()
