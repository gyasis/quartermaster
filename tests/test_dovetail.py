import math
import pytest

from quartermaster.joint_strategy import JointSpec, JointType, pick_joint
from quartermaster.joints.dovetail import dovetail_path_2d


def _spec(angle=10, tail_count=1, **extra):
    return JointSpec(
        JointType.DOVETAIL,
        {"angle_deg": angle, "tail_count": tail_count, **extra},
        pin_count=0,
    )


class TestDovetailPath:
    def test_single_tail_returns_six_points(self):
        path = dovetail_path_2d(_spec(), thickness=6.0, seam_length=80.0)
        assert len(path) == 6

    def test_endpoints_at_seam_extents_on_cut_line(self):
        path = dovetail_path_2d(_spec(), thickness=6.0, seam_length=80.0)
        assert path[0] == (0.0, -40.0)
        assert path[-1] == (0.0, +40.0)

    def test_tail_protrudes_in_positive_n(self):
        path = dovetail_path_2d(_spec(), thickness=6.0, seam_length=80.0)
        # Middle two points are the wide end of the tail
        n_values = [p[0] for p in path]
        assert max(n_values) > 0
        assert path[2][0] == path[3][0], "tail's wide-end vertices share the same n'"
        assert path[2][0] == max(n_values), "wide end is the maximum protrusion"

    def test_tail_outline_traces_in_order(self):
        """The path is NOT monotonic in s' — the tail's wide end protrudes
        slightly outside its narrow base. That's the dovetail flare. But the
        sequence is still consistent: cut line up, around the tail, cut line up."""
        path = dovetail_path_2d(_spec(), thickness=6.0, seam_length=80.0)
        # Cut line below the tail
        assert path[1][1] > path[0][1]
        # Cross the tail base (going up in s', mostly): negative side base->top is OUTWARD
        assert path[2][1] < path[1][1], "tail's lower-outer corner is wider than base"
        # Across the tail's far edge
        assert path[3][1] > path[2][1]
        # Back to base on the upper side: also outward
        assert path[4][1] < path[3][1], "tail's upper-outer corner is wider than base"
        # Cut line above the tail
        assert path[5][1] > path[4][1]

    def test_top_wider_than_base(self):
        """The defining feature of a dovetail: wide end > narrow end."""
        path = dovetail_path_2d(_spec(angle=10), thickness=6.0, seam_length=80.0)
        base_width = path[4][1] - path[1][1]   # base is path[1] to path[4]
        top_width  = path[3][1] - path[2][1]   # top is path[2] to path[3]
        assert top_width > base_width, f"dovetail must flare: top={top_width}, base={base_width}"

    def test_flare_matches_angle(self):
        path = dovetail_path_2d(_spec(angle=10), thickness=6.0, seam_length=80.0)
        protrusion = path[2][0]
        base_width = path[4][1] - path[1][1]
        top_width  = path[3][1] - path[2][1]
        flare_per_side = (top_width - base_width) / 2
        expected_flare = protrusion * math.tan(math.radians(10))
        assert flare_per_side == pytest.approx(expected_flare)

    def test_default_protrusion_scales_with_thickness(self):
        thin = dovetail_path_2d(_spec(), thickness=6.0, seam_length=80.0)[2][0]
        thick = dovetail_path_2d(_spec(), thickness=10.0, seam_length=80.0)[2][0]
        assert thick > thin

    def test_protrusion_floor_at_8mm(self):
        """Below ~5mm thickness, the 1.5*t default would be tiny — we floor at 8mm."""
        path = dovetail_path_2d(_spec(), thickness=4.0, seam_length=80.0)
        assert path[2][0] == pytest.approx(8.0)

    def test_explicit_params_override_defaults(self):
        spec = _spec(protrusion_mm=12.0, base_width_mm=20.0)
        path = dovetail_path_2d(spec, thickness=6.0, seam_length=80.0)
        assert path[2][0] == pytest.approx(12.0)
        base_width = path[4][1] - path[1][1]
        assert base_width == pytest.approx(20.0)

    def test_base_too_wide_for_seam_rejected(self):
        spec = _spec(base_width_mm=200)
        with pytest.raises(ValueError, match="won't fit"):
            dovetail_path_2d(spec, thickness=6.0, seam_length=80.0)

    def test_negative_seam_rejected(self):
        with pytest.raises(ValueError):
            dovetail_path_2d(_spec(), thickness=6.0, seam_length=-1)

    def test_invalid_angle_rejected(self):
        with pytest.raises(ValueError):
            dovetail_path_2d(_spec(angle=50), thickness=6.0, seam_length=80.0)
        with pytest.raises(ValueError):
            dovetail_path_2d(_spec(angle=0), thickness=6.0, seam_length=80.0)

    def test_multi_tail_not_yet_supported(self):
        with pytest.raises(NotImplementedError):
            dovetail_path_2d(_spec(tail_count=3), thickness=6.0, seam_length=200.0)

    def test_rejects_non_dovetail_spec(self):
        spec = JointSpec(JointType.SCARF, {"ratio": 8, "overlap_mm": 32}, 0)
        with pytest.raises(ValueError):
            dovetail_path_2d(spec, thickness=6.0, seam_length=80.0)


class TestIntegrationWithPicker:
    """When the picker chooses DOVETAIL, the path generator must accept the spec."""

    def test_picker_dovetail_short_seam_5_to_8mm(self):
        spec = pick_joint(thickness=6.0, seam_length=80.0)
        assert spec.joint == JointType.DOVETAIL
        path = dovetail_path_2d(spec, thickness=6.0, seam_length=80.0)
        assert len(path) == 6

    def test_picker_dovetail_short_seam_3_to_5mm(self):
        # 3-5mm short seam also picks dovetail
        spec = pick_joint(thickness=4.0, seam_length=60.0)
        assert spec.joint == JointType.DOVETAIL
        path = dovetail_path_2d(spec, thickness=4.0, seam_length=60.0)
        assert len(path) == 6
