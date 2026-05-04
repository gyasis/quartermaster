"""Dovetail joint geometry.

A dovetail's defining feature is a *trapezoidal* tail that flares outward —
the wide end is at the protruding side, the narrow end at the base. When the
two halves are pulled apart, the flare resists pull-out: the only way to
separate them is to slide along the seam axis.

Geometry lives in (n', s') seam-along coords (top view of the plate at the
cut location). n' is perpendicular to the seam (the cut direction) and
points from LEFT half toward RIGHT half. s' is along the seam.

For tail_count=1, the path forms a single centered tail protruding from
LEFT half into RIGHT half's territory.
"""
from __future__ import annotations
import math

from ..joint_strategy import JointSpec, JointType


# Default proportions when not overridden in spec.params.
# Picked to give a visually-recognizable dovetail without burning glue area:
#   protrusion = max(1.5 * thickness, 8mm)        — mechanical lock depth
#   base_width = 4 * thickness                    — proportional to stock
def _resolve_geometry(spec: JointSpec, thickness: float) -> tuple[float, float, float]:
    """Return (protrusion_mm, base_width_mm, angle_rad) from spec + defaults."""
    angle_deg     = spec.params.get("angle_deg", 8.0)
    protrusion_mm = spec.params.get("protrusion_mm", max(1.5 * thickness, 8.0))
    base_width_mm = spec.params.get("base_width_mm", 4.0 * thickness)
    if protrusion_mm <= 0:
        raise ValueError(f"protrusion_mm must be > 0, got {protrusion_mm}")
    if base_width_mm <= 0:
        raise ValueError(f"base_width_mm must be > 0, got {base_width_mm}")
    if angle_deg <= 0 or angle_deg >= 45:
        raise ValueError(f"angle_deg must be in (0, 45), got {angle_deg}")
    return protrusion_mm, base_width_mm, math.radians(angle_deg)


def dovetail_path_2d(
    spec:        JointSpec,
    thickness:   float,
    seam_length: float,
) -> list[tuple[float, float]]:
    """Cut path between LEFT and RIGHT halves in (n', s') seam-along coords.

    LEFT half is at n' < path; RIGHT at n' > path. The path runs from
    -seam/2 to +seam/2 in s' and stays at n' = 0 except where each tail
    protrudes (n' = +protrusion_mm).

    For N tails: returns 4N+2 points. Tails are distributed evenly along the
    seam with N+1 equal gaps (one before the first tail, one between each
    pair, one after the last). Each tail flares outward by `angle_deg`.
    """
    if spec.joint != JointType.DOVETAIL:
        raise ValueError(f"dovetail_path_2d requires a DOVETAIL spec, got {spec.joint}")
    if seam_length <= 0:
        raise ValueError(f"seam_length must be > 0, got {seam_length}")

    tail_count = spec.params.get("tail_count", 1)
    if tail_count < 1:
        raise ValueError(f"tail_count must be >= 1, got {tail_count}")

    protrusion, base_width, angle_rad = _resolve_geometry(spec, thickness)
    flare      = protrusion * math.tan(angle_rad)
    top_width  = base_width + 2 * flare
    half_seam  = seam_length / 2
    half_base  = base_width  / 2
    half_top   = top_width   / 2

    gap = (seam_length - tail_count * base_width) / (tail_count + 1)
    if gap <= 0:
        raise ValueError(
            f"{tail_count} tails of base_width={base_width} won't fit on seam={seam_length} "
            f"(gap would be {gap:.2f})"
        )

    points: list[tuple[float, float]] = [(0.0, -half_seam)]
    for i in range(tail_count):
        center = -half_seam + (i + 1) * gap + (i + 0.5) * base_width
        points.extend([
            (0.0,         center - half_base),  # base near-side
            (+protrusion, center - half_top ),  # outer near-side (flared OUT past base)
            (+protrusion, center + half_top ),  # outer far-side
            (0.0,         center + half_base),  # base far-side
        ])
    points.append((0.0, +half_seam))
    return points
