from __future__ import annotations
from dataclasses import dataclass
import math

from ..joint_strategy import JointSpec, JointType
from ..plane import CutPlane

Vec3 = tuple[float, float, float]


def _norm(v: Vec3) -> Vec3:
    m = math.sqrt(v[0] * v[0] + v[1] * v[1] + v[2] * v[2])
    if m == 0:
        raise ValueError("zero-length vector")
    return (v[0] / m, v[1] / m, v[2] / m)


def _cross(a: Vec3, b: Vec3) -> Vec3:
    return (
        a[1] * b[2] - a[2] * b[1],
        a[2] * b[0] - a[0] * b[2],
        a[0] * b[1] - a[1] * b[0],
    )


def _dot(a: Vec3, b: Vec3) -> float:
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def _rotate(v: Vec3, axis: Vec3, angle_rad: float) -> Vec3:
    """Rodrigues' rotation: v rotated around unit axis by angle (right-hand rule)."""
    k = _norm(axis)
    c = math.cos(angle_rad)
    s = math.sin(angle_rad)
    kxv = _cross(k, v)
    kdv = _dot(k, v)
    return (
        v[0] * c + kxv[0] * s + k[0] * kdv * (1 - c),
        v[1] * c + kxv[1] * s + k[1] * kdv * (1 - c),
        v[2] * c + kxv[2] * s + k[2] * kdv * (1 - c),
    )


@dataclass(frozen=True)
class Pin:
    center:   Vec3
    axis:     Vec3
    diameter: float = 3.0
    length:   float = 6.0


def scarf_angle_rad(spec: JointSpec, thickness: float) -> float:
    """Angle between the scarf cut surface and the plate plane: atan(thickness/overlap)."""
    if spec.joint != JointType.SCARF:
        raise ValueError(f"scarf_angle_rad requires a SCARF spec, got {spec.joint}")
    overlap = spec.params["overlap_mm"]
    if overlap <= 0:
        raise ValueError(f"scarf overlap_mm must be > 0, got {overlap}")
    return math.atan2(thickness, overlap)


def scarf_path_2d(spec: JointSpec, thickness: float) -> list[tuple[float, float]]:
    """Cut path in (n', t') seam-cross-section coords, centered on the cut.

    n' is the in-plane direction perpendicular to the seam; t' is the thickness
    axis. Origin is at base_plane.point.

    Smooth scarf (table_mm == 0)  -> 2 points: the two endpoints of the diagonal.
    Tabled scarf  (table_mm > 0)  -> 4 points: upper diagonal end, table start,
                                     table end, lower diagonal end. The table
                                     is a perpendicular step at t' = 0.

    The table provides a mechanical lock against in-plane pull and a
    self-registering ledge during glue-up — at the cost of a tighter
    tolerance requirement at the step.
    """
    if spec.joint != JointType.SCARF:
        raise ValueError(f"scarf_path_2d requires a SCARF spec, got {spec.joint}")
    overlap = spec.params["overlap_mm"]
    table   = spec.params.get("table_mm", 0.0)
    if overlap <= 0:
        raise ValueError(f"overlap_mm must be > 0, got {overlap}")
    if table < 0:
        raise ValueError(f"table_mm must be >= 0, got {table}")
    if table >= overlap:
        raise ValueError(f"table_mm ({table}) must be < overlap_mm ({overlap})")

    half_t = thickness / 2
    half_o = overlap / 2

    if table == 0:
        return [(-half_o, +half_t), (+half_o, -half_t)]

    half_table = table / 2
    return [
        (-half_o,     +half_t),
        (-half_table,  0.0   ),
        (+half_table,  0.0   ),
        (+half_o,     -half_t),
    ]


def scarf_plane(base: CutPlane, spec: JointSpec, thickness: float) -> CutPlane:
    """Return a CutPlane representing the scarf-tilted cut.

    The cut surface tilts around the seam axis by (90° - scarf_angle) so the
    surface lies almost flat relative to the plate (matches a real scarf joint:
    a long shallow ramp through the stock thickness).
    """
    if spec.joint != JointType.SCARF:
        raise ValueError(f"scarf_plane requires a SCARF spec, got {spec.joint}")
    angle = scarf_angle_rad(spec, thickness)
    rot = angle - math.pi / 2
    new_n = _rotate(_norm(base.normal), _norm(base.seam_axis), rot)
    return CutPlane(point=base.point, normal=new_n, seam_axis=base.seam_axis)


def pin_locations(
    base:         CutPlane,
    spec:         JointSpec,
    seam_origin:  Vec3,
    seam_length:  float,
    thickness:    float,
    pin_diameter: float = 3.0,
) -> list[Pin]:
    """Distribute alignment pins evenly along the seam.

    Pins are placed at fractions i/(N+1) along the seam from seam_origin, so
    N=2 pins land at 1/3 and 2/3 of the seam length. Pin axis is the scarf
    plane's normal so the pin is perpendicular to the slanted scarf face.
    """
    if spec.pin_count <= 0:
        return []
    s = _norm(base.seam_axis)
    sp = scarf_plane(base, spec, thickness)
    pin_axis = sp.normal
    pin_length = max(6.0, 2.0 * thickness)
    pins: list[Pin] = []
    for i in range(1, spec.pin_count + 1):
        d = seam_length * i / (spec.pin_count + 1)
        center = (
            seam_origin[0] + s[0] * d,
            seam_origin[1] + s[1] * d,
            seam_origin[2] + s[2] * d,
        )
        pins.append(Pin(center=center, axis=pin_axis, diameter=pin_diameter, length=pin_length))
    return pins
