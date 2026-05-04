import math
import pytest

from quartermaster.joint_strategy import JointSpec, JointType, pick_joint
from quartermaster.joints.sliding_dovetail import sliding_dovetail_profile_2d


def _spec(angle=12, **extra):
    return JointSpec(JointType.SLIDING_DOVETAIL, {"angle_deg": angle, **extra}, pin_count=0)


class TestSlidingDovetailProfile:
    def test_returns_four_points(self):
        prof = sliding_dovetail_profile_2d(_spec(depth_mm=8, base_width_mm=6), thickness=12.0)
        assert len(prof) == 4

    def test_base_at_n_zero(self):
        prof = sliding_dovetail_profile_2d(_spec(depth_mm=8, base_width_mm=6), thickness=12.0)
        assert prof[0][0] == 0.0
        assert prof[3][0] == 0.0

    def test_tip_at_n_depth(self):
        prof = sliding_dovetail_profile_2d(_spec(depth_mm=8, base_width_mm=6), thickness=12.0)
        assert prof[1][0] == 8.0
        assert prof[2][0] == 8.0

    def test_top_wider_than_base(self):
        prof = sliding_dovetail_profile_2d(_spec(depth_mm=8, base_width_mm=6), thickness=12.0)
        base = prof[3][1] - prof[0][1]
        top  = prof[2][1] - prof[1][1]
        assert top > base

    def test_flare_matches_angle(self):
        prof = sliding_dovetail_profile_2d(_spec(angle=12, depth_mm=10, base_width_mm=6), thickness=20)
        flare = (prof[2][1] - prof[1][1] - (prof[3][1] - prof[0][1])) / 2
        expected = 10 * math.tan(math.radians(12))
        assert flare == pytest.approx(expected)

    def test_top_too_wide_rejected(self):
        # angle=20 + depth=10 + base=10: top_width = 10 + 2*10*tan(20°) = 17.28; thickness=15 → fails
        with pytest.raises(ValueError, match="top_width"):
            sliding_dovetail_profile_2d(_spec(angle=20, depth_mm=10, base_width_mm=10), thickness=15)

    def test_invalid_angle_rejected(self):
        with pytest.raises(ValueError):
            sliding_dovetail_profile_2d(_spec(angle=0, depth_mm=8, base_width_mm=6), thickness=12)
        with pytest.raises(ValueError):
            sliding_dovetail_profile_2d(_spec(angle=50, depth_mm=8, base_width_mm=6), thickness=12)

    def test_negative_depth_rejected(self):
        with pytest.raises(ValueError):
            sliding_dovetail_profile_2d(_spec(depth_mm=-1, base_width_mm=6), thickness=12)

    def test_rejects_non_sliding_spec(self):
        spec = JointSpec(JointType.DOVETAIL, {"angle_deg": 10, "tail_count": 1}, 0)
        with pytest.raises(ValueError):
            sliding_dovetail_profile_2d(spec, thickness=12)


class TestPickerIntegration:
    def test_picker_returns_sliding_dovetail_for_thick_long(self):
        spec = pick_joint(thickness=12.0, seam_length=400.0)
        assert spec.joint == JointType.SLIDING_DOVETAIL
        prof = sliding_dovetail_profile_2d(spec, thickness=12.0)
        assert len(prof) == 4

    def test_picker_provides_depth_mm(self):
        spec = pick_joint(thickness=10.0, seam_length=400.0)
        assert "depth_mm" in spec.params
