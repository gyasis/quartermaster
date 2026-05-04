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
        scene  = context.scene

        # --- Quick start fixtures ----------
        box = layout.box()
        box.label(text="Quick start (test fixtures)", icon="MESH_CUBE")
        box.operator("quartermaster.add_test_block",     text="Add Test Block (300x200x4 -> scarf)")
        box.operator("quartermaster.add_dovetail_block", text="Add Dovetail Block (80x60x6 -> dove)")

        # --- 1. Cut plane ----------
        layout.separator()
        col = layout.column(align=True)
        col.label(text="1. Cut plane", icon="EMPTY_ARROWS")
        col.operator("quartermaster.add_cut_plane",  text="Add Cut Plane")
        col.operator("quartermaster.snap_cut_plane", text="Snap to Longest Axis")

        # --- 2. Position ----------
        layout.separator()
        col = layout.column(align=True)
        col.label(text="2. Position the QM_CutPlane")
        col.label(text="    drag gizmo arrows or G/R")

        # --- 3. Joint config ----------
        layout.separator()
        col = layout.column(align=True)
        col.label(text="3. Joint config", icon="MOD_BOOLEAN")

        col.prop(scene, "qm_joint_override", text="Joint")

        is_dovetail_override = getattr(scene, "qm_joint_override", "AUTO") == "DOVETAIL"
        sub = col.column(align=True)
        sub.enabled = is_dovetail_override
        sub.prop(scene, "qm_tail_count")
        sub.prop(scene, "qm_dovetail_angle")

        sub2 = col.column(align=True)
        sub2.enabled = not is_dovetail_override   # table only meaningful for scarf
        sub2.prop(scene, "qm_table_mm", slider=True)

        # --- 4. Cut ----------
        layout.separator()
        col = layout.column(align=True)
        col.label(text="4. Select target mesh, then cut")
        col.label(text="    (ctrl-click extras to union)", icon="BLANK1")
        col.operator("quartermaster.execute_cut", text="Cut Along Plane")

        # --- Status ----------
        layout.separator()
        box = layout.box()
        box.label(text="Status", icon="INFO")
        target = context.active_object
        plane  = _find_cut_plane()
        target_str = (
            target.name if target and target.type == "MESH" and not target.get(QM_CUT_PLANE_PROP)
            else "(select a mesh)"
        )
        plane_str = plane.name if plane else "(none yet)"
        box.label(text=f"Target: {target_str}")
        box.label(text=f"Plane:  {plane_str}")


CLASSES = (QM_PT_Panel,)
