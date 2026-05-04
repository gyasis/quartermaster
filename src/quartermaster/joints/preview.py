"""Unified joint preview: returns 2D line segments showing what each joint
type looks like, so users can visualize before committing to a cut.

Each preview is a list of line segments in the cut plane's local 2D frame:
  - axes "n_t": perpendicular-to-seam cross-section view. Used by scarf,
    half-lap, sliding dovetail — joints whose cutter extrudes along the seam.
  - axes "n_s": top-down view of the seam. Used by dovetail and finger —
    joints whose cutter extrudes through thickness.

The Blender side translates these 2D segments to 3D edges in the cut
plane's local frame (n_axis, s_axis or t_axis depending on `axes`).
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import Tuple

from ..joint_strategy import JointSpec, JointType
from .scarf            import scarf_path_2d
from .dovetail         import dovetail_path_2d
from .finger           import finger_path_2d
from .box              import box_path_2d
from .half_lap         import half_lap_path_2d
from .sliding_dovetail import sliding_dovetail_profile_2d


Point2D    = Tuple[float, float]
LineSeg    = Tuple[Point2D, Point2D]


@dataclass(frozen=True)
class JointPreview:
    lines_2d:    list[LineSeg]
    axes:        str           # "n_t" or "n_s"
    description: str


def _open_polyline(points: list[Point2D]) -> list[LineSeg]:
    """Connect a sequence of points with line segments (no closure)."""
    return [(points[i], points[i + 1]) for i in range(len(points) - 1)]


def _closed_polygon(points: list[Point2D]) -> list[LineSeg]:
    """Connect points and close the loop."""
    n = len(points)
    return [(points[i], points[(i + 1) % n]) for i in range(n)]


def joint_preview(
    spec:         JointSpec,
    thickness:    float,
    seam_length:  float = 200.0,
) -> JointPreview:
    """Return a wireframe preview for the given JointSpec.

    `thickness` and `seam_length` shape the preview to match what the actual
    cut would produce. `seam_length` only matters for joints whose features
    distribute along the seam (dovetail, finger).
    """
    j = spec.joint

    if j == JointType.SCARF:
        path  = scarf_path_2d(spec, thickness)
        ratio = spec.params.get("ratio", "?")
        table = spec.params.get("table_mm", 0)
        kind  = f"tabled (table {table:.1f}mm)" if table > 0 else "smooth"
        return JointPreview(
            lines_2d=_open_polyline(path),
            axes="n_t",
            description=f"Scarf {ratio}:1 ({kind})",
        )

    if j == JointType.HALF_LAP:
        path    = half_lap_path_2d(spec, thickness)
        overlap = abs(path[0][0])
        return JointPreview(
            lines_2d=_open_polyline(path),
            axes="n_t",
            description=f"Half-lap, {overlap:.1f}mm lap",
        )

    if j == JointType.SLIDING_DOVETAIL:
        profile   = sliding_dovetail_profile_2d(spec, thickness)
        angle_deg = spec.params.get("angle_deg", "?")
        return JointPreview(
            lines_2d=_closed_polygon(profile),
            axes="n_t",
            description=f"Sliding dovetail, {angle_deg}° flare",
        )

    if j == JointType.DOVETAIL:
        path        = dovetail_path_2d(spec, thickness, seam_length)
        tail_count  = spec.params.get("tail_count", 1)
        angle_deg   = spec.params.get("angle_deg", "?")
        return JointPreview(
            lines_2d=_open_polyline(path),
            axes="n_s",
            description=f"Dovetail, {tail_count} tail(s), {angle_deg}° flare",
        )

    if j == JointType.FINGER:
        path   = finger_path_2d(spec, thickness, seam_length)
        # 4N+2 points -> N fingers
        n_fingers = (len(path) - 2) // 4
        return JointPreview(
            lines_2d=_open_polyline(path),
            axes="n_s",
            description=f"Finger joint, {n_fingers} fingers",
        )

    if j == JointType.BOX:
        path = box_path_2d(spec, thickness, seam_length)
        finger_count = spec.params.get("finger_count", 3)
        return JointPreview(
            lines_2d=_open_polyline(path),
            axes="n_s",
            description=f"Box joint, {finger_count} square fingers",
        )

    raise NotImplementedError(f"No preview for joint type {j.value}")
