import pytest
from quartermaster.plane import CutPlane


def _close(a, b, tol=1e-6):
    return all(abs(x - y) < tol for x, y in zip(a, b))


class TestThicknessAxis:
    """The thickness axis is derived from the cut plane orientation, not assumed.
    This is what makes the picker plane-agnostic."""

    def test_yz_cut_thickness_is_z(self):
        cp = CutPlane(point=(156.7, 0, 1.5), normal=(1, 0, 0), seam_axis=(0, 1, 0))
        assert _close(cp.thickness_axis, (0, 0, 1))

    def test_xz_cut_thickness_is_z(self):
        cp = CutPlane(point=(0, 50, 1.5), normal=(0, 1, 0), seam_axis=(1, 0, 0))
        # (0,1,0) × (1,0,0) = (0,0,-1) — same axis, opposite sign
        ax = cp.thickness_axis
        assert ax[0] == pytest.approx(0)
        assert ax[1] == pytest.approx(0)
        assert abs(ax[2]) == pytest.approx(1.0)

    def test_xy_cut_thickness_is_y(self):
        # Plate standing on its edge, cut from above
        cp = CutPlane(point=(0, 0, 50), normal=(0, 0, 1), seam_axis=(1, 0, 0))
        # (0,0,1) × (1,0,0) = (0,1,0)
        assert _close(cp.thickness_axis, (0, 1, 0))

    def test_unnormalized_inputs_are_normalized(self):
        cp = CutPlane(point=(0, 0, 0), normal=(2, 0, 0), seam_axis=(0, 5, 0))
        assert _close(cp.thickness_axis, (0, 0, 1))


class TestMeasure:
    """measure() extracts the (thickness, seam_length) scalars the picker needs."""

    def test_axis_aligned_plate_yz_cut(self):
        # Sketch.003 in world coords
        cp = CutPlane(point=(156.7, 0, 1.5), normal=(1, 0, 0), seam_axis=(0, 1, 0))
        bbox_min = (-1.6, 0.4, 0.0)
        bbox_max = (314.4, 214.5, 3.0)
        thickness, seam_length = cp.measure(bbox_min, bbox_max)
        assert thickness == pytest.approx(3.0)
        assert seam_length == pytest.approx(214.1, abs=0.1)

    def test_xz_cut_swaps_seam_and_thickness_correctly(self):
        # Same plate, different cut direction: cut perpendicular to Y, seam along X
        cp = CutPlane(point=(0, 50, 1.5), normal=(0, 1, 0), seam_axis=(1, 0, 0))
        bbox_min = (-1.6, 0.4, 0.0)
        bbox_max = (314.4, 214.5, 3.0)
        thickness, seam_length = cp.measure(bbox_min, bbox_max)
        assert thickness == pytest.approx(3.0)            # still Z
        assert seam_length == pytest.approx(316.0, abs=0.1)  # now X
