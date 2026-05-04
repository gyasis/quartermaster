import pytest

from quartermaster.joint_strategy import JointSpec, JointType, pick_joint
from quartermaster.joints.box import box_path_2d


def _spec(**params):
    return JointSpec(JointType.BOX, dict(params), pin_count=0)


class TestBoxPath:
    def test_three_fingers_returns_14_points(self):
        path = box_path_2d(_spec(finger_count=3, depth_mm=12), thickness=12, seam_length=80)
        assert len(path) == 4 * 3 + 2

    def test_endpoints_at_seam_extents(self):
        path = box_path_2d(_spec(finger_count=3, depth_mm=12), thickness=12, seam_length=80)
        assert path[0]  == (0.0, -40.0)
        assert path[-1] == (0.0, +40.0)

    def test_default_finger_count_is_3(self):
        path = box_path_2d(_spec(depth_mm=12), thickness=12, seam_length=80)
        assert (len(path) - 2) // 4 == 3

    def test_default_depth_equals_thickness(self):
        path = box_path_2d(_spec(finger_count=3), thickness=12, seam_length=80)
        outer_n_values = {p[0] for p in path if p[0] > 0}
        assert outer_n_values == {12.0}

    def test_equal_finger_and_gap_widths_by_default(self):
        # finger_width = seam / (2N+1) = 70/7 = 10
        path = box_path_2d(_spec(finger_count=3, depth_mm=12), thickness=12, seam_length=70)
        finger_width = path[4][1] - path[1][1]
        assert finger_width == pytest.approx(10.0)

    def test_outer_corners_have_no_flare(self):
        # Box joints are rectangular — defining feature vs dovetail
        path = box_path_2d(_spec(finger_count=3, depth_mm=12), thickness=12, seam_length=80)
        for i in range(3):
            base_near, outer_near, outer_far, base_far = path[1 + 4*i : 5 + 4*i]
            assert base_near[1] == outer_near[1]
            assert base_far[1]  == outer_far[1]

    def test_explicit_finger_width_override(self):
        path = box_path_2d(_spec(finger_count=2, finger_width_mm=10, depth_mm=12),
                           thickness=12, seam_length=60)
        finger_width = path[4][1] - path[1][1]
        assert finger_width == pytest.approx(10.0)

    def test_too_many_fingers_rejected(self):
        with pytest.raises(ValueError, match="won't fit"):
            box_path_2d(_spec(finger_count=20, depth_mm=12, finger_width_mm=10),
                        thickness=12, seam_length=20)

    def test_zero_finger_count_rejected(self):
        with pytest.raises(ValueError):
            box_path_2d(_spec(finger_count=0, depth_mm=12), thickness=12, seam_length=80)

    def test_negative_depth_rejected(self):
        with pytest.raises(ValueError):
            box_path_2d(_spec(finger_count=3, depth_mm=-1), thickness=12, seam_length=80)

    def test_rejects_non_box_spec(self):
        spec = JointSpec(JointType.FINGER, {"pitch_mm": 12, "depth_mm": 6}, 0)
        with pytest.raises(ValueError):
            box_path_2d(spec, thickness=12, seam_length=80)


class TestPickerIntegration:
    def test_picker_box_for_thick_short(self):
        spec = pick_joint(thickness=12.0, seam_length=80.0)
        assert spec.joint == JointType.BOX
        path = box_path_2d(spec, thickness=12.0, seam_length=80.0)
        assert len(path) == 14   # 3 fingers default
