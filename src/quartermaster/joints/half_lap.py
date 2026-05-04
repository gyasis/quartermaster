"""Half-lap joint geometry.

A half-lap is the simplest mechanical joint: each piece keeps half its
thickness for an `overlap_mm` distance past the cut line, on opposite faces.
LEFT keeps the top half across the lap; RIGHT keeps the bottom half. They
interlock at z=0 with substantial glue area but no flare or pull-out
resistance — pure friction + adhesive.

The cut path lives in the (n', t') seam-cross-section plane and traces a
Z-shape:
    (-overlap, +half_t) -> (-overlap, 0) -> (+overlap, 0) -> (+overlap, -half_t)

The cutter (the +n' side of this path, extruded along the seam axis)
naturally splits into two convex boxes — top-half above z=0 in the +n
half-space, and bottom-half below z=0 in the +n half-space, offset from
each other in n by 2*overlap. We build it as a multi-island mesh of two
convex prisms, which the EXACT boolean solver handles reliably.
"""
from __future__ import annotations

from ..joint_strategy import JointSpec, JointType


def half_lap_path_2d(
    spec:      JointSpec,
    thickness: float,
) -> list[tuple[float, float]]:
    """Z-shape cut path in (n', t') coords.

    Returns 4 points forming the boundary between LEFT and RIGHT halves.
    """
    if spec.joint != JointType.HALF_LAP:
        raise ValueError(f"half_lap_path_2d requires HALF_LAP spec, got {spec.joint}")
    if thickness <= 0:
        raise ValueError(f"thickness must be > 0, got {thickness}")

    overlap = spec.params.get("overlap_mm", max(thickness * 2.0, 8.0))
    if overlap <= 0:
        raise ValueError(f"overlap_mm must be > 0, got {overlap}")

    half_t = thickness / 2
    return [
        (-overlap, +half_t),
        (-overlap, 0.0),
        (+overlap, 0.0),
        (+overlap, -half_t),
    ]
