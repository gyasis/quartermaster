import pytest

from quartermaster.joint_strategy import JointSpec, JointType, pick_joint
from quartermaster.joints.preview import joint_preview, JointPreview


def _spec(joint, **params):
    return JointSpec(joint, dict(params), pin_count=0)


class TestPreviewBasics:
    def test_smooth_scarf_yields_one_segment(self):
        prev = joint_preview(_spec(JointType.SCARF, ratio=8, overlap_mm=32), thickness=4)
        assert prev.axes == "n_t"
        assert len(prev.lines_2d) == 1
        assert "smooth" in prev.description.lower()

    def test_tabled_scarf_yields_three_segments(self):
        prev = joint_preview(_spec(JointType.SCARF, ratio=8, overlap_mm=32, table_mm=8), thickness=4)
        assert len(prev.lines_2d) == 3
        assert "tabled" in prev.description.lower()

    def test_half_lap_yields_three_segments(self):
        prev = joint_preview(_spec(JointType.HALF_LAP, overlap_mm=10), thickness=6)
        assert prev.axes == "n_t"
        assert len(prev.lines_2d) == 3
        assert "10" in prev.description

    def test_sliding_dovetail_yields_closed_quad(self):
        prev = joint_preview(_spec(JointType.SLIDING_DOVETAIL, angle_deg=12, depth_mm=8, base_width_mm=6), thickness=12)
        # Closed trapezoid -> 4 segments
        assert prev.axes == "n_t"
        assert len(prev.lines_2d) == 4
        # First segment's start should equal last segment's end (closed loop)
        assert prev.lines_2d[0][0] == prev.lines_2d[-1][1]

    def test_single_dovetail(self):
        prev = joint_preview(_spec(JointType.DOVETAIL, angle_deg=10, tail_count=1), thickness=6, seam_length=80)
        assert prev.axes == "n_s"
        # 6-point path -> 5 segments
        assert len(prev.lines_2d) == 5
        assert "1 tail" in prev.description

    def test_multi_tail_dovetail(self):
        prev = joint_preview(_spec(JointType.DOVETAIL, angle_deg=10, tail_count=3), thickness=4, seam_length=200)
        # 14-point path (4N+2) -> 13 segments
        assert len(prev.lines_2d) == 13
        assert "3 tail" in prev.description

    def test_finger_joint(self):
        prev = joint_preview(_spec(JointType.FINGER, pitch_mm=12, depth_mm=6), thickness=4, seam_length=200)
        assert prev.axes == "n_s"
        # Number of fingers = floor(seam/pitch) = 16 -> 4*16+2 = 66 points -> 65 segments
        assert len(prev.lines_2d) == 65
        assert "16 fingers" in prev.description


class TestPreviewMatchesPicker:
    """Whatever the picker chooses for a given (thickness, seam_length) combo,
    joint_preview should accept that spec and return a non-empty preview."""

    @pytest.mark.parametrize("thickness,seam_length", [
        (1.5,  200),
        (3.0,  200),
        (4.0,   60),
        (4.0,  200),
        (4.0,  500),
        (6.0,   80),
        (6.0,  300),
        (12.0, 400),
    ])
    def test_picker_output_previewable(self, thickness, seam_length):
        spec = pick_joint(thickness=thickness, seam_length=seam_length)
        try:
            prev = joint_preview(spec, thickness=thickness, seam_length=seam_length)
        except NotImplementedError:
            pytest.skip(f"{spec.joint.value} preview not implemented yet")
        assert len(prev.lines_2d) >= 1
        assert prev.axes in ("n_t", "n_s")
        assert prev.description


class TestPreviewLineGeometry:
    def test_smooth_scarf_endpoints_at_top_and_bottom(self):
        prev = joint_preview(_spec(JointType.SCARF, ratio=8, overlap_mm=32), thickness=4)
        seg = prev.lines_2d[0]
        # Smooth scarf: from (-16, +2) to (+16, -2)
        assert seg[0] == (-16.0, +2.0)
        assert seg[1] == (+16.0, -2.0)

    def test_half_lap_has_horizontal_step(self):
        prev = joint_preview(_spec(JointType.HALF_LAP, overlap_mm=10), thickness=6)
        # The middle segment is the horizontal step at z=0
        a, b = prev.lines_2d[1]
        assert a[1] == 0.0
        assert b[1] == 0.0
