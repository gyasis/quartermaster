"""Box joint geometry.

A box joint is a finger joint with thicker, more spaced fingers — typically
parameterized by an explicit `finger_count` rather than by pitch. The picker
returns BOX for thick stock (>=8mm) on short seams, where a few large fingers
beat many small ones.

Geometrically identical to a finger joint (rectangular through-fingers, no
flare). The cutter mesh and Blender pipeline are reused via _cut_with_path.
"""
from __future__ import annotations

from ..joint_strategy import JointSpec, JointType


def box_path_2d(
    spec:        JointSpec,
    thickness:   float,
    seam_length: float,
) -> list[tuple[float, float]]:
    """Cut path between LEFT and RIGHT in (n', s') seam-along coords.

    Default: equal-width fingers and gaps, each = seam_length / (2*N + 1)
    (so N fingers + N+1 gaps fill the seam exactly). 4N+2 points.
    """
    if spec.joint != JointType.BOX:
        raise ValueError(f"box_path_2d requires BOX spec, got {spec.joint}")
    if seam_length <= 0:
        raise ValueError(f"seam_length must be > 0, got {seam_length}")

    finger_count = spec.params.get("finger_count", 3)
    depth        = spec.params.get("depth_mm",     thickness)

    if finger_count < 1:
        raise ValueError(f"finger_count must be >= 1, got {finger_count}")
    if depth <= 0:
        raise ValueError(f"depth_mm must be > 0, got {depth}")

    finger_width = spec.params.get("finger_width_mm",
                                   seam_length / (2 * finger_count + 1))
    if finger_width <= 0:
        raise ValueError(f"finger_width_mm must be > 0, got {finger_width}")

    gap_width = (seam_length - finger_count * finger_width) / (finger_count + 1)
    if gap_width <= 0:
        raise ValueError(
            f"{finger_count} fingers of width {finger_width:.2f} won't fit on seam {seam_length}"
        )

    half_seam   = seam_length / 2
    half_finger = finger_width / 2

    points: list[tuple[float, float]] = [(0.0, -half_seam)]
    for i in range(finger_count):
        center = -half_seam + (i + 1) * gap_width + (i + 0.5) * finger_width
        points.extend([
            (0.0,    center - half_finger),
            (+depth, center - half_finger),
            (+depth, center + half_finger),
            (0.0,    center + half_finger),
        ])
    points.append((0.0, +half_seam))
    return points
