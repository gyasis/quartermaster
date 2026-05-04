"""Tests for pure-Python helpers in the Blender cut pipeline.

These functions don't import bpy at call time, so we can exercise them in
plain pytest. Importing quartermaster.blender.cut at the module level is
fine because all bpy imports are lazy (inside functions).
"""
import math
import pytest

from quartermaster.blender.cut import _offset_polygon, _path_indentations


def _close(a, b, tol=1e-6):
    return all(abs(x - y) < tol for x, y in zip(a, b))


class TestOffsetPolygon:
    def test_zero_distance_returns_input(self):
        sq = [(0.0, 0.0), (1.0, 0.0), (1.0, 1.0), (0.0, 1.0)]
        assert _offset_polygon(sq, 0.0) == sq

    def test_unit_square_grows_by_2x_distance(self):
        # Square of side 1 offset outward by 0.1 -> square of side 1.2
        sq = [(0.0, 0.0), (1.0, 0.0), (1.0, 1.0), (0.0, 1.0)]
        out = _offset_polygon(sq, 0.1)
        # Each side should be 1.2 long
        side = math.hypot(out[1][0] - out[0][0], out[1][1] - out[0][1])
        assert side == pytest.approx(1.2)
        # Centroid should match
        cx = sum(p[0] for p in out) / 4
        cy = sum(p[1] for p in out) / 4
        assert cx == pytest.approx(0.5)
        assert cy == pytest.approx(0.5)

    def test_rectangle_preserves_aspect(self):
        rect = [(0.0, 0.0), (10.0, 0.0), (10.0, 5.0), (0.0, 5.0)]
        out = _offset_polygon(rect, 0.5)
        width  = out[1][0] - out[0][0]   # 11.0
        height = out[2][1] - out[1][1]   # 6.0
        assert width  == pytest.approx(11.0)
        assert height == pytest.approx( 6.0)

    def test_dovetail_trapezoid(self):
        # Dovetail tail outline: trapezoid with flare. Outward offset preserves
        # the flare angle; each edge moves perpendicular by `distance`.
        trap = [(0.0, -8.0), (8.0, -8.71), (8.0, +8.71), (0.0, +8.0)]
        out = _offset_polygon(trap, 0.2)
        # The protrusion side (n' = 8) should now be at n' > 8
        assert out[1][0] > 8.0
        assert out[2][0] > 8.0
        # The base side (n' = 0) should be at n' < 0
        assert out[0][0] < 0.0
        assert out[3][0] < 0.0

    def test_negative_distance_shrinks(self):
        sq = [(-1.0, -1.0), (1.0, -1.0), (1.0, 1.0), (-1.0, 1.0)]
        out = _offset_polygon(sq, -0.1)
        side = out[1][0] - out[0][0]
        assert side == pytest.approx(1.8)


class TestPathIndentations:
    def test_dovetail_single_tail_yields_one_polygon(self):
        path = [
            (0.0, -100.0),
            (0.0, -8.0), (8.0, -8.71), (8.0, +8.71), (0.0, +8.0),
            (0.0, +100.0),
        ]
        polys = _path_indentations(path)
        assert len(polys) == 1
        assert polys[0] == [(0.0, -8.0), (8.0, -8.71), (8.0, +8.71), (0.0, +8.0)]

    def test_path_with_no_bulges_yields_no_polygons(self):
        # A straight cut path has no n' > 0 segments
        path = [(0.0, -50.0), (0.0, +50.0)]
        assert _path_indentations(path) == []

    def test_two_separate_bulges(self):
        # Synthesize a path with two indentations
        path = [
            (0.0, -100.0),
            (0.0, -50.0), (5.0, -50.0), (5.0, -30.0), (0.0, -30.0),
            (0.0, +30.0), (5.0, +30.0), (5.0, +50.0), (0.0, +50.0),
            (0.0, +100.0),
        ]
        polys = _path_indentations(path)
        assert len(polys) == 2
