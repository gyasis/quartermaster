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

        joint_mode = getattr(scene, "qm_joint_override", "AUTO")
        is_dovetail = joint_mode == "DOVETAIL"
        is_half_lap = joint_mode == "HALF_LAP"
        is_sliding  = joint_mode == "SLIDING_DOVETAIL"
        is_scarf    = joint_mode == "AUTO"  # picker often picks SCARF; allow table_mm

        sub_dt = col.column(align=True)
        sub_dt.enabled = is_dovetail
        sub_dt.prop(scene, "qm_tail_count")

        sub_angle = col.column(align=True)
        sub_angle.enabled = is_dovetail or is_sliding
        sub_angle.prop(scene, "qm_dovetail_angle")

        sub_lap = col.column(align=True)
        sub_lap.enabled = is_half_lap
        sub_lap.prop(scene, "qm_overlap_mm", slider=True)

        sub_table = col.column(align=True)
        sub_table.enabled = is_scarf  # tabled scarf only when picker chooses scarf
        sub_table.prop(scene, "qm_table_mm", slider=True)

        col.prop(scene, "qm_tolerance_mm", slider=True)

        # --- 4. Preview & Cut ----------
        layout.separator()
        col = layout.column(align=True)
        col.label(text="4. Preview & Cut", icon="MOD_BOOLEAN")
        col.operator("quartermaster.preview_joint", text="Preview Joint", icon="HIDE_OFF")
        col.label(text="    (ctrl-click extras to union)")
        col.operator("quartermaster.execute_cut",   text="Cut Along Plane", icon="MOD_BOOLEAN")

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

        # --- Cleanup ----------
        layout.separator()
        layout.operator("quartermaster.reset_scene", text="Reset Scene (clear QM)", icon="TRASH")


CLASSES = (QM_PT_Panel,)
