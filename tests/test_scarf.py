import math
import pytest

from quartermaster.joint_strategy import JointSpec, JointType, pick_joint
from quartermaster.plane import CutPlane
from quartermaster.joints.scarf import (
    Pin,
    scarf_angle_rad,
    scarf_plane,
    scarf_path_2d,
    pin_locations,
)


def _close(a, b, tol=1e-6):
    return all(abs(x - y) < tol for x, y in zip(a, b))


class TestScarfAngle:
    """The defining geometric quantity: arctan(thickness / overlap_mm)."""

    def test_8_to_1_at_3mm(self):
        spec = JointSpec(JointType.SCARF, {"ratio": 8, "overlap_mm": 24.0}, pin_count=0)
        assert scarf_angle_rad(spec, 3.0) == pytest.approx(math.atan2(3.0, 24.0))

    def test_12_to_1_at_2mm(self):
        spec = JointSpec(JointType.SCARF, {"ratio": 12, "overlap_mm": 24.0}, pin_count=0)
        assert scarf_angle_rad(spec, 2.0) == pytest.approx(math.atan2(2.0, 24.0))

    def test_rejects_non_scarf_spec(self):
        spec = JointSpec(JointType.HALF_LAP, {}, 0)
        with pytest.raises(ValueError):
            scarf_angle_rad(spec, 3.0)

    def test_rejects_zero_overlap(self):
        spec = JointSpec(JointType.SCARF, {"ratio": 8, "overlap_mm": 0.0}, 0)
        with pytest.raises(ValueError):
            scarf_angle_rad(spec, 3.0)


class TestScarfPlaneOrientation:
    """For a YZ cut on a flat plate, the scarf normal is mostly +Z."""

    def test_normal_for_yz_cut_on_flat_plate(self):
        base = CutPlane(point=(156.7, 0, 1.5), normal=(1, 0, 0), seam_axis=(0, 1, 0))
        spec = JointSpec(JointType.SCARF, {"ratio": 8, "overlap_mm": 24.0}, pin_count=2)
        sp = scarf_plane(base, spec, thickness=3.0)
        angle = math.atan2(3.0, 24.0)
        assert sp.normal[0] == pytest.approx(math.sin(angle))
        assert sp.normal[1] == pytest.approx(0, abs=1e-9)
        assert sp.normal[2] == pytest.approx(math.cos(angle))

    def test_normal_for_xz_cut(self):
        # Cut perpendicular to Y, seam along X. Thickness axis = n × s = (0,1,0) × (1,0,0) = (0,0,-1)
        base = CutPlane(point=(0, 50, 1.5), normal=(0, 1, 0), seam_axis=(1, 0, 0))
        spec = JointSpec(JointType.SCARF, {"ratio": 8, "overlap_mm": 24.0}, pin_count=0)
        sp = scarf_plane(base, spec, thickness=3.0)
        angle = math.atan2(3.0, 24.0)
        # Tilted from +Y toward -Z: (0, sin(angle), -cos(angle))
        assert sp.normal[0] == pytest.approx(0, abs=1e-9)
        assert sp.normal[1] == pytest.approx(math.sin(angle))
        assert sp.normal[2] == pytest.approx(-math.cos(angle))

    def test_seam_axis_unchanged(self):
        base = CutPlane(point=(0, 0, 0), normal=(1, 0, 0), seam_axis=(0, 1, 0))
        spec = JointSpec(JointType.SCARF, {"ratio": 8, "overlap_mm": 24.0}, pin_count=0)
        sp = scarf_plane(base, spec, thickness=3.0)
        assert sp.seam_axis == base.seam_axis

    def test_point_unchanged(self):
        base = CutPlane(point=(156.7, 0, 1.5), normal=(1, 0, 0), seam_axis=(0, 1, 0))
        spec = JointSpec(JointType.SCARF, {"ratio": 8, "overlap_mm": 24.0}, pin_count=0)
        sp = scarf_plane(base, spec, thickness=3.0)
        assert sp.point == base.point

    def test_rejects_non_scarf_spec(self):
        base = CutPlane(point=(0, 0, 0), normal=(1, 0, 0), seam_axis=(0, 1, 0))
        spec = JointSpec(JointType.HALF_LAP, {}, 0)
        with pytest.raises(ValueError):
            scarf_plane(base, spec, thickness=3.0)


class TestPinLocations:
    def test_two_pins_evenly_spaced_along_seam(self):
        base = CutPlane(point=(156.7, 0, 1.5), normal=(1, 0, 0), seam_axis=(0, 1, 0))
        spec = JointSpec(JointType.SCARF, {"ratio": 8, "overlap_mm": 24.0}, pin_count=2)
        pins = pin_locations(
            base, spec,
            seam_origin=(156.7, 0, 1.5),
            seam_length=215,
            thickness=3.0,
        )
        assert len(pins) == 2
        ys = sorted(p.center[1] for p in pins)
        assert ys[0] == pytest.approx(215 / 3)
        assert ys[1] == pytest.approx(2 * 215 / 3)

    def test_pins_on_seam_line(self):
        # All pin centers should lie on the line from seam_origin along seam_axis
        base = CutPlane(point=(156.7, 0, 1.5), normal=(1, 0, 0), seam_axis=(0, 1, 0))
        spec = JointSpec(JointType.SCARF, {"ratio": 8, "overlap_mm": 24.0}, pin_count=3)
        pins = pin_locations(
            base, spec,
            seam_origin=(156.7, 0, 1.5),
            seam_length=300,
            thickness=4.0,
        )
        assert len(pins) == 3
        for p in pins:
            assert p.center[0] == pytest.approx(156.7)
            assert p.center[2] == pytest.approx(1.5)

    def test_pin_axis_matches_scarf_normal(self):
        base = CutPlane(point=(156.7, 0, 1.5), normal=(1, 0, 0), seam_axis=(0, 1, 0))
        spec = JointSpec(JointType.SCARF, {"ratio": 8, "overlap_mm": 24.0}, pin_count=2)
        pins = pin_locations(
            base, spec,
            seam_origin=(156.7, 0, 1.5),
            seam_length=215,
            thickness=3.0,
        )
        sp = scarf_plane(base, spec, thickness=3.0)
        for p in pins:
            assert _close(p.axis, sp.normal, tol=1e-9)

    def test_zero_pin_count_returns_empty(self):
        base = CutPlane(point=(0, 0, 0), normal=(1, 0, 0), seam_axis=(0, 1, 0))
        spec = JointSpec(JointType.SCARF, {"ratio": 8, "overlap_mm": 24.0}, pin_count=0)
        assert pin_locations(base, spec, seam_origin=(0, 0, 0), seam_length=200, thickness=3.0) == []

    def test_default_pin_diameter_3mm(self):
        base = CutPlane(point=(0, 0, 0), normal=(1, 0, 0), seam_axis=(0, 1, 0))
        spec = JointSpec(JointType.SCARF, {"ratio": 8, "overlap_mm": 24.0}, pin_count=2)
        pins = pin_locations(base, spec, seam_origin=(0, 0, 0), seam_length=200, thickness=3.0)
        assert all(p.diameter == 3.0 for p in pins)

    def test_pin_length_at_least_double_thickness(self):
        # Pins must penetrate both halves; length scales with stock
        base = CutPlane(point=(0, 0, 0), normal=(1, 0, 0), seam_axis=(0, 1, 0))
        spec = JointSpec(JointType.SCARF, {"ratio": 8, "overlap_mm": 40.0}, pin_count=2)
        pins = pin_locations(base, spec, seam_origin=(0, 0, 0), seam_length=200, thickness=5.0)
        assert all(p.length >= 10.0 for p in pins)


class TestScarfPath2D:
    """The 2D cut profile drives both smooth bisection and tabled cutter-mesh
    generation. Locking it down here means the geometry stays predictable as
    the joint logic evolves."""

    def test_smooth_scarf_returns_two_points(self):
        spec = JointSpec(JointType.SCARF, {"ratio": 8, "overlap_mm": 32.0}, pin_count=0)
        path = scarf_path_2d(spec, thickness=4.0)
        assert path == [(-16.0, +2.0), (+16.0, -2.0)]

    def test_zero_table_equivalent_to_omitted(self):
        a = JointSpec(JointType.SCARF, {"ratio": 8, "overlap_mm": 32.0}, 0)
        b = JointSpec(JointType.SCARF, {"ratio": 8, "overlap_mm": 32.0, "table_mm": 0.0}, 0)
        assert scarf_path_2d(a, 4.0) == scarf_path_2d(b, 4.0)

    def test_tabled_scarf_returns_four_points(self):
        spec = JointSpec(JointType.SCARF, {"ratio": 8, "overlap_mm": 32.0, "table_mm": 8.0}, 0)
        path = scarf_path_2d(spec, thickness=4.0)
        assert len(path) == 4
        assert path[0] == pytest.approx((-16.0, +2.0))
        assert path[-1] == pytest.approx((+16.0, -2.0))

    def test_table_sits_at_mid_thickness(self):
        spec = JointSpec(JointType.SCARF, {"ratio": 8, "overlap_mm": 32.0, "table_mm": 8.0}, 0)
        path = scarf_path_2d(spec, thickness=4.0)
        assert path[1][1] == pytest.approx(0.0)
        assert path[2][1] == pytest.approx(0.0)

    def test_table_centered_on_cut(self):
        spec = JointSpec(JointType.SCARF, {"ratio": 8, "overlap_mm": 32.0, "table_mm": 8.0}, 0)
        path = scarf_path_2d(spec, thickness=4.0)
        assert path[1][0] == pytest.approx(-4.0)
        assert path[2][0] == pytest.approx(+4.0)

    def test_path_strictly_monotonic_in_n(self):
        spec = JointSpec(JointType.SCARF, {"ratio": 8, "overlap_mm": 32.0, "table_mm": 8.0}, 0)
        path = scarf_path_2d(spec, thickness=4.0)
        for a, b in zip(path, path[1:]):
            assert b[0] > a[0], f"non-monotonic: {a} -> {b}"

    def test_negative_table_rejected(self):
        spec = JointSpec(JointType.SCARF, {"ratio": 8, "overlap_mm": 32.0, "table_mm": -1.0}, 0)
        with pytest.raises(ValueError):
            scarf_path_2d(spec, 4.0)

    def test_table_equals_overlap_rejected(self):
        spec = JointSpec(JointType.SCARF, {"ratio": 8, "overlap_mm": 32.0, "table_mm": 32.0}, 0)
        with pytest.raises(ValueError):
            scarf_path_2d(spec, 4.0)

    def test_rejects_non_scarf_spec(self):
        spec = JointSpec(JointType.HALF_LAP, {}, 0)
        with pytest.raises(ValueError):
            scarf_path_2d(spec, 4.0)


class TestSketch003ReferenceBuild:
    """End-to-end: picker output feeds straight into the geometry generator."""

    def test_picker_to_scarf_plane_to_pins(self):
        spec = pick_joint(thickness=3.0, seam_length=215)
        base = CutPlane(point=(156.7, 0, 1.5), normal=(1, 0, 0), seam_axis=(0, 1, 0))

        sp = scarf_plane(base, spec, thickness=3.0)
        # Confirms picker + generator agree on overlap geometry
        expected_angle = math.atan2(3.0, 24.0)
        assert sp.normal[2] == pytest.approx(math.cos(expected_angle))

        pins = pin_locations(base, spec, seam_origin=(156.7, 0, 1.5), seam_length=215, thickness=3.0)
        assert len(pins) == 2
