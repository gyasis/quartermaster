import pytest

from quartermaster.joint_strategy import JointSpec, JointType
from quartermaster.joints.half_lap import half_lap_path_2d


def _spec(**extra):
    return JointSpec(JointType.HALF_LAP, dict(extra), pin_count=0)


class TestHalfLapPath:
    def test_returns_four_points(self):
        path = half_lap_path_2d(_spec(overlap_mm=10), thickness=4.0)
        assert len(path) == 4

    def test_top_at_plus_half_thickness(self):
        path = half_lap_path_2d(_spec(overlap_mm=10), thickness=4.0)
        assert path[0] == (-10.0, +2.0)

    def test_bottom_at_minus_half_thickness(self):
        path = half_lap_path_2d(_spec(overlap_mm=10), thickness=4.0)
        assert path[-1] == (+10.0, -2.0)

    def test_step_at_z_zero(self):
        path = half_lap_path_2d(_spec(overlap_mm=10), thickness=4.0)
        assert path[1][1] == 0.0
        assert path[2][1] == 0.0

    def test_step_n_extents_match_overlap(self):
        path = half_lap_path_2d(_spec(overlap_mm=10), thickness=4.0)
        assert path[1][0] == -10.0
        assert path[2][0] == +10.0

    def test_default_overlap_scales_with_thickness(self):
        path = half_lap_path_2d(_spec(), thickness=6.0)
        # default = max(thickness * 2, 8) = 12
        assert path[1][0] == pytest.approx(-12.0)

    def test_default_overlap_floor_at_8mm(self):
        # For very thin stock, default would be 2*t = small. Should floor at 8mm.
        path = half_lap_path_2d(_spec(), thickness=2.0)
        assert path[1][0] == pytest.approx(-8.0)

    def test_negative_overlap_rejected(self):
        with pytest.raises(ValueError):
            half_lap_path_2d(_spec(overlap_mm=-1), thickness=4.0)

    def test_zero_thickness_rejected(self):
        with pytest.raises(ValueError):
            half_lap_path_2d(_spec(overlap_mm=10), thickness=0)

    def test_rejects_non_half_lap_spec(self):
        spec = JointSpec(JointType.SCARF, {"ratio": 8, "overlap_mm": 32}, 0)
        with pytest.raises(ValueError):
            half_lap_path_2d(spec, thickness=4.0)
