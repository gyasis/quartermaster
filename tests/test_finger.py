import pytest

from quartermaster.joint_strategy import JointSpec, JointType, pick_joint
from quartermaster.joints.finger import finger_path_2d


def _spec(pitch=12, depth=6, **extra):
    return JointSpec(
        JointType.FINGER,
        {"pitch_mm": pitch, "depth_mm": depth, **extra},
        pin_count=0,
    )


class TestFingerPath:
    def test_returns_4n_plus_2_points(self):
        # 200mm seam / 12mm pitch = 16 fingers
        path = finger_path_2d(_spec(), thickness=4.0, seam_length=200.0)
        assert len(path) == 4 * 16 + 2

    def test_endpoints_at_seam_extents(self):
        path = finger_path_2d(_spec(), thickness=4.0, seam_length=200.0)
        assert path[0]  == (0.0, -100.0)
        assert path[-1] == (0.0, +100.0)

    def test_outer_corners_have_no_flare(self):
        """Defining feature of finger vs dovetail: outer corners share s' with base corners."""
        path = finger_path_2d(_spec(), thickness=4.0, seam_length=200.0)
        # Each finger contributes 4 points: base_near, outer_near, outer_far, base_far
        # For a finger (i): path[1 + 4i .. 4 + 4i]
        for i in range(4):  # check first 4 fingers
            base_near  = path[1 + 4 * i]
            outer_near = path[2 + 4 * i]
            outer_far  = path[3 + 4 * i]
            base_far   = path[4 + 4 * i]
            assert base_near[1] == outer_near[1], f"finger {i} flares (it shouldn't)"
            assert base_far[1]  == outer_far[1],  f"finger {i} flares (it shouldn't)"

    def test_finger_protrusion_matches_depth(self):
        path = finger_path_2d(_spec(depth=8), thickness=4.0, seam_length=200.0)
        outer_n_values = {p[0] for p in path if p[0] > 0}
        assert outer_n_values == {8.0}

    def test_pitch_determines_finger_count(self):
        big   = finger_path_2d(_spec(pitch=20), thickness=4.0, seam_length=200.0)
        small = finger_path_2d(_spec(pitch=10), thickness=4.0, seam_length=200.0)
        n_big   = (len(big)   - 2) // 4
        n_small = (len(small) - 2) // 4
        assert n_small > n_big

    def test_explicit_finger_width_override(self):
        spec = _spec(pitch=20, finger_width_mm=4.0)  # 4mm finger, 16mm gap
        path = finger_path_2d(spec, thickness=4.0, seam_length=200.0)
        # finger width = base_far - base_near
        finger_width = path[4][1] - path[1][1]
        assert finger_width == pytest.approx(4.0)

    def test_zero_pitch_rejected(self):
        with pytest.raises(ValueError):
            finger_path_2d(_spec(pitch=0), thickness=4.0, seam_length=200.0)

    def test_negative_depth_rejected(self):
        with pytest.raises(ValueError):
            finger_path_2d(_spec(depth=-1), thickness=4.0, seam_length=200.0)

    def test_finger_width_must_be_less_than_pitch(self):
        spec = _spec(pitch=10, finger_width_mm=10)
        with pytest.raises(ValueError):
            finger_path_2d(spec, thickness=4.0, seam_length=200.0)

    def test_rejects_non_finger_spec(self):
        spec = JointSpec(JointType.SCARF, {"ratio": 8, "overlap_mm": 32}, 0)
        with pytest.raises(ValueError):
            finger_path_2d(spec, thickness=4.0, seam_length=200.0)


class TestIntegrationWithPicker:
    def test_picker_finger_long_seam_3_to_5mm(self):
        spec = pick_joint(thickness=4.0, seam_length=500.0)
        assert spec.joint == JointType.FINGER
        path = finger_path_2d(spec, thickness=4.0, seam_length=500.0)
        # Must produce at least one finger
        assert len(path) >= 6

    def test_picker_finger_5_to_8mm(self):
        spec = pick_joint(thickness=6.0, seam_length=300.0)
        assert spec.joint == JointType.FINGER
        path = finger_path_2d(spec, thickness=6.0, seam_length=300.0)
        assert len(path) >= 6
