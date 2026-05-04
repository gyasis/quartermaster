"""Finger (box) joint geometry.

Finger joints are like dovetails but with rectangular protrusions instead of
trapezoidal — no flare. They give the same self-aligning property as a
multi-tail dovetail but rely entirely on glue (or pins) for pull-out
resistance, since the rectangular fingers don't lock against extraction.

For the picker, fingers are the default at long seams in the 3-8mm thickness
band — they self-align over distance better than a single big dovetail.
"""
from __future__ import annotations

from ..joint_strategy import JointSpec, JointType


def finger_path_2d(
    spec:        JointSpec,
    thickness:   float,
    seam_length: float,
) -> list[tuple[float, float]]:
    """Cut path between LEFT and RIGHT halves in (n', s') coords.

    LEFT half has N rectangular fingers protruding +n'; RIGHT has matching
    sockets. Path: 4N+2 points, same shape as multi-tail dovetail but with
    the outer corners at the same s' as the base corners (rectangular).

    Spec params:
      pitch_mm:    one full repeat (finger_width + adjacent gap)
      depth_mm:    finger protrusion in n'
      finger_width_mm: optional override (default = pitch_mm / 2)
    """
    if spec.joint != JointType.FINGER:
        raise ValueError(f"finger_path_2d requires a FINGER spec, got {spec.joint}")
    if seam_length <= 0:
        raise ValueError(f"seam_length must be > 0, got {seam_length}")

    pitch = spec.params.get("pitch_mm")
    depth = spec.params.get("depth_mm")
    if pitch is None or pitch <= 0:
        raise ValueError(f"pitch_mm must be > 0, got {pitch}")
    if depth is None or depth <= 0:
        raise ValueError(f"depth_mm must be > 0, got {depth}")

    finger_width = spec.params.get("finger_width_mm", pitch / 2)
    if finger_width <= 0 or finger_width >= pitch:
        raise ValueError(f"finger_width_mm must be in (0, pitch_mm)")

    n_fingers = max(1, int(seam_length / pitch))
    gap_width = (seam_length - n_fingers * finger_width) / (n_fingers + 1)
    if gap_width <= 0:
        raise ValueError(
            f"{n_fingers} fingers of width {finger_width} won't fit on seam {seam_length}"
        )

    half_seam   = seam_length / 2
    half_finger = finger_width / 2

    points: list[tuple[float, float]] = [(0.0, -half_seam)]
    for i in range(n_fingers):
        center = -half_seam + (i + 1) * gap_width + (i + 0.5) * finger_width
        points.extend([
            (0.0,    center - half_finger),  # base near-side
            (+depth, center - half_finger),  # outer near-side (no flare!)
            (+depth, center + half_finger),  # outer far-side
            (0.0,    center + half_finger),  # base far-side
        ])
    points.append((0.0, +half_seam))
    return points
