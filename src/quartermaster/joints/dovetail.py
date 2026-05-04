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
    -seam/2 to +seam/2 in s' and stays at n' = 0 except where the tail
    protrudes (n' = +protrusion_mm).

    Returns 6 points for tail_count=1; multi-tail paths are not yet supported.
    """
    if spec.joint != JointType.DOVETAIL:
        raise ValueError(f"dovetail_path_2d requires a DOVETAIL spec, got {spec.joint}")
    if seam_length <= 0:
        raise ValueError(f"seam_length must be > 0, got {seam_length}")

    tail_count = spec.params.get("tail_count", 1)
    if tail_count != 1:
        raise NotImplementedError(f"only tail_count=1 supported (got {tail_count})")

    protrusion, base_width, angle_rad = _resolve_geometry(spec, thickness)
    flare      = protrusion * math.tan(angle_rad)
    top_width  = base_width + 2 * flare

    if base_width >= seam_length:
        raise ValueError(
            f"dovetail base_width ({base_width}) >= seam ({seam_length}); "
            f"tail won't fit on this seam"
        )

    half_seam = seam_length / 2
    half_base = base_width  / 2
    half_top  = top_width   / 2

    return [
        (0.0,         -half_seam),  # bottom of seam, on cut line
        (0.0,         -half_base),  # start of dovetail base (LEFT side of tail)
        (+protrusion, -half_top ),  # outer corner, lower side of tail
        (+protrusion, +half_top ),  # outer corner, upper side
        (0.0,         +half_base),  # end of dovetail base
        (0.0,         +half_seam),  # top of seam, on cut line
    ]
