"""Sliding-dovetail joint geometry.

A sliding dovetail is a dovetail rotated 90 degrees from the through-dovetail:
the trapezoidal flare lives in the THICKNESS direction instead of along the
seam. The two halves slide together along the seam axis (s'), with the
flare locking against pull-out perpendicular to the seam.

Profile is a 4-point trapezoid in (n', t'), extruded along the full seam:
    (0, -half_base) -> (depth, -half_top) -> (depth, +half_top) -> (0, +half_base)

Where half_top > half_base, giving the dovetail flare. LEFT gets a tenon
matching this profile; RIGHT gets a matching groove.
"""
from __future__ import annotations
import math

from ..joint_strategy import JointSpec, JointType


def sliding_dovetail_profile_2d(
    spec:      JointSpec,
    thickness: float,
) -> list[tuple[float, float]]:
    """Trapezoid profile of the tenon in (n', t') coords.

    The tenon's narrow end (base) is at n'=0 (the cut surface); the wide
    end (top) is at n'=+depth. Flare angle is `angle_deg` per side from
    the normal to the cut surface.
    """
    if spec.joint != JointType.SLIDING_DOVETAIL:
        raise ValueError(f"sliding_dovetail_profile_2d requires SLIDING_DOVETAIL, got {spec.joint}")
    if thickness <= 0:
        raise ValueError(f"thickness must be > 0, got {thickness}")

    angle_deg  = spec.params.get("angle_deg", 12.0)
    depth      = spec.params.get("depth_mm",      max(thickness * 0.6, 8.0))
    base_width = spec.params.get("base_width_mm", max(thickness * 0.5, 6.0))

    if not (0 < angle_deg < 45):
        raise ValueError(f"angle_deg must be in (0, 45), got {angle_deg}")
    if depth <= 0:
        raise ValueError(f"depth_mm must be > 0, got {depth}")
    if base_width <= 0:
        raise ValueError(f"base_width_mm must be > 0, got {base_width}")

    flare      = depth * math.tan(math.radians(angle_deg))
    top_width  = base_width + 2 * flare

    if top_width >= thickness:
        raise ValueError(
            f"tenon top_width ({top_width:.2f}) >= thickness ({thickness}); "
            f"reduce angle, depth, or base_width"
        )

    half_base = base_width / 2
    half_top  = top_width  / 2

    return [
        (0.0,   -half_base),
        (depth, -half_top ),
        (depth, +half_top ),
        (0.0,   +half_base),
    ]
