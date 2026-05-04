from __future__ import annotations
from dataclasses import dataclass
import math

Vec3 = tuple[float, float, float]


def _norm(v: Vec3) -> Vec3:
    m = math.sqrt(v[0] * v[0] + v[1] * v[1] + v[2] * v[2])
    if m == 0:
        raise ValueError("zero-length vector cannot be normalized")
    return (v[0] / m, v[1] / m, v[2] / m)


def _cross(a: Vec3, b: Vec3) -> Vec3:
    return (
        a[1] * b[2] - a[2] * b[1],
        a[2] * b[0] - a[0] * b[2],
        a[0] * b[1] - a[1] * b[0],
    )


@dataclass(frozen=True)
class CutPlane:
    """A cut plane plus the seam axis that runs along it.

    The picker is plane-agnostic: whatever direction is perpendicular to both
    the plane normal and the seam axis becomes the "thickness axis" — the
    direction along which we measure stock thickness for joint selection.
    """
    point:     Vec3
    normal:    Vec3
    seam_axis: Vec3

    @property
    def thickness_axis(self) -> Vec3:
        return _norm(_cross(_norm(self.normal), _norm(self.seam_axis)))

    def measure(self, bbox_min: Vec3, bbox_max: Vec3) -> tuple[float, float]:
        """Return (thickness, seam_length) for an axis-aligned bounding box.

        Projects the AABB extents onto the thickness and seam axes. For tilted
        cut planes on non-axis-aligned parts, the caller should compute these
        scalars directly from part geometry rather than relying on the AABB.
        """
        size = (
            bbox_max[0] - bbox_min[0],
            bbox_max[1] - bbox_min[1],
            bbox_max[2] - bbox_min[2],
        )
        t_axis = self.thickness_axis
        s_axis = _norm(self.seam_axis)
        thickness   = abs(t_axis[0]) * size[0] + abs(t_axis[1]) * size[1] + abs(t_axis[2]) * size[2]
        seam_length = abs(s_axis[0]) * size[0] + abs(s_axis[1]) * size[1] + abs(s_axis[2]) * size[2]
        return thickness, seam_length
