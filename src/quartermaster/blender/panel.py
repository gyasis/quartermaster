"""Quartermaster N-panel (View3D > N > Quartermaster)."""
from __future__ import annotations
import bpy

from .adapter import QM_CUT_PLANE_PROP


def _find_cut_plane():
    return next((o for o in bpy.data.objects if o.get(QM_CUT_PLANE_PROP)), None)


class QM_PT_Panel(bpy.types.Panel):
    bl_idname      = "QM_PT_panel"
    bl_label       = "Quartermaster"
    bl_space_type  = "VIEW_3D"
    bl_region_type = "UI"
    bl_category    = "Quartermaster"

    def draw(self, context):
        layout = self.layout

        # Quick start — clean fixtures for the smoke test
        box = layout.box()
        box.label(text="Quick start (test fixtures)", icon="MESH_CUBE")
        box.operator("quartermaster.add_test_block",     text="Add Test Block (300x200x4 -> scarf)")
        box.operator("quartermaster.add_dovetail_block", text="Add Dovetail Block (80x60x6 -> dovetail)")

        layout.separator()
        col = layout.column(align=True)
        col.label(text="1. Add cut plane", icon="EMPTY_ARROWS")
        col.operator("quartermaster.add_cut_plane", text="Add Cut Plane")

        layout.separator()
        col = layout.column(align=True)
        col.label(text="2. Drag the QM_CutPlane")
        col.label(text="    G = move,  R = rotate")

        layout.separator()
        col = layout.column(align=True)
        col.label(text="3. Select mesh, then cut", icon="MOD_BOOLEAN")
        col.prop(context.scene, "qm_use_table_lock", text="Locked (tabled) joint")
        col.operator("quartermaster.execute_cut", text="Cut Along Plane")

        layout.separator()
        box = layout.box()
        box.label(text="Status", icon="INFO")
        target = context.active_object
        plane  = _find_cut_plane()
        target_str = (target.name if target and target.type == "MESH"
                      and not target.get(QM_CUT_PLANE_PROP) else "(select a mesh)")
        plane_str  = plane.name if plane else "(none yet)"
        box.label(text=f"Target: {target_str}")
        box.label(text=f"Plane:  {plane_str}")


CLASSES = (QM_PT_Panel,)
