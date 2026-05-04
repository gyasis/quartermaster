from __future__ import annotations
from dataclasses import dataclass
from enum import Enum
from typing import Optional


class JointType(str, Enum):
    SCARF            = "scarf"
    HALF_LAP         = "half_lap"
    FINGER           = "finger"
    DOVETAIL         = "dovetail"
    BOX              = "box"
    SLIDING_DOVETAIL = "sliding_dovetail"


# Minimum stock thickness (mm) at which each joint becomes mechanically viable on FDM.
# Crossing each threshold "unlocks" that joint family.
MIN_THICKNESS_MM: dict[JointType, float] = {
    JointType.SCARF:            0.0,
    JointType.HALF_LAP:         3.0,
    JointType.FINGER:           3.0,
    JointType.DOVETAIL:         3.0,
    JointType.BOX:              5.0,
    JointType.SLIDING_DOVETAIL: 8.0,
}


@dataclass(frozen=True)
class JointSpec:
    joint:     JointType
    params:    dict
    pin_count: int = 0
    rationale: str = ""

    def to_dict(self) -> dict:
        return {
            "joint":     self.joint.value,
            "params":    dict(self.params),
            "pin_count": self.pin_count,
            "rationale": self.rationale,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "JointSpec":
        return cls(
            joint=JointType(d["joint"]),
            params=dict(d.get("params", {})),
            pin_count=int(d.get("pin_count", 0)),
            rationale=d.get("rationale", ""),
        )


def viable_joints(thickness: float) -> set[JointType]:
    if thickness <= 0:
        raise ValueError(f"thickness must be > 0, got {thickness}")
    return {j for j, t in MIN_THICKNESS_MM.items() if thickness >= t}


def pick_joint(
    thickness:     float,
    seam_length:   float,
    seam_visible:  bool = False,
    in_plane_load: bool = False,
    override:      Optional[JointType] = None,
) -> JointSpec:
    if thickness <= 0:
        raise ValueError(f"thickness must be > 0, got {thickness}")
    if seam_length <= 0:
        raise ValueError(f"seam_length must be > 0, got {seam_length}")

    if override is not None:
        if thickness < MIN_THICKNESS_MM[override]:
            raise ValueError(
                f"override joint {override.value} not viable at thickness {thickness}mm "
                f"(needs >= {MIN_THICKNESS_MM[override]}mm)"
            )
        return _build(override, thickness, seam_length, rationale="manual override")

    short_seam = seam_length < 100
    long_seam  = seam_length > 300

    if seam_visible:
        return _build(JointType.SCARF, thickness, seam_length,
                      rationale="visible seam: scarf blends optically")

    if thickness < 3:
        return _build(JointType.SCARF, thickness, seam_length,
                      rationale="thin stock: scarf is the only viable joint")

    if 3 <= thickness < 5:
        if short_seam:
            return _build(JointType.DOVETAIL, thickness, seam_length,
                          rationale="short 3-5mm seam: single dovetail beats fragile fingers")
        if long_seam:
            return _build(JointType.FINGER, thickness, seam_length,
                          rationale="long 3-5mm seam: zig-zag fingers self-align over distance")
        return _build(JointType.SCARF, thickness, seam_length,
                      rationale="medium 3-5mm seam: scarf 8:1 multiplies glue area, no fragile features")

    if 5 <= thickness < 8:
        if short_seam:
            return _build(JointType.DOVETAIL, thickness, seam_length,
                          rationale="short 5-8mm seam: clean single dovetail")
        return _build(JointType.FINGER, thickness, seam_length,
                      rationale="5-8mm seam: multi-finger / box-style for repeating mechanical lock")

    # >= 8mm
    if short_seam:
        return _build(JointType.BOX, thickness, seam_length,
                      rationale="short thick seam: box joint with large fingers")
    return _build(JointType.SLIDING_DOVETAIL, thickness, seam_length,
                  rationale="long thick seam: sliding dovetail mechanically locks against pull")


def _build(joint: JointType, thickness: float, seam_length: float, rationale: str = "") -> JointSpec:
    pin_count = _pin_count(seam_length)
    if joint == JointType.SCARF:
        ratio = 12 if thickness < 3 else 8
        return JointSpec(joint, {"ratio": ratio, "overlap_mm": ratio * thickness}, pin_count, rationale)
    if joint == JointType.HALF_LAP:
        return JointSpec(joint, {"overlap_mm": max(8.0, 3 * thickness)}, pin_count, rationale)
    if joint == JointType.FINGER:
        pitch = 12 if thickness < 5 else 15
        return JointSpec(joint, {"pitch_mm": pitch, "depth_mm": min(thickness * 1.6, 8)}, pin_count, rationale)
    if joint == JointType.DOVETAIL:
        angle = 8 if thickness < 5 else 10
        tail_count = 1 if seam_length < 100 else 2
        return JointSpec(joint, {"angle_deg": angle, "tail_count": tail_count}, 0, rationale)
    if joint == JointType.BOX:
        return JointSpec(joint, {"finger_count": 3, "depth_mm": thickness}, 0, rationale)
    if joint == JointType.SLIDING_DOVETAIL:
        return JointSpec(joint, {"angle_deg": 12, "depth_mm": thickness * 0.6}, 0, rationale)
    raise ValueError(f"unknown joint type {joint}")


def _pin_count(seam_length: float) -> int:
    if seam_length < 100:
        return 0
    if seam_length < 300:
        return 2
    return max(2, int(seam_length / 150))
