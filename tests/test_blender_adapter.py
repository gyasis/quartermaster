"""Tests for the parts of the Blender adapter that don't require bpy.

Anything that calls into bpy (cuttable_copy, add_cut_plane_helper) is exercised
by an integration script run inside Blender, not here.
"""
import math

import pytest

from quartermaster.blender.adapter import cut_plane_from_matrix


class _FakeMatrix:
    """Minimal duck-type stand-in for mathutils.Matrix."""
    def __init__(self, translation, basis):
        self.translation = _Vec3(*translation)
        self._basis = basis  # 3x3 list-of-cols; each col is (x,y,z)

    def to_3x3(self):
        return _FakeRot(self._basis)


class _FakeRot:
    def __init__(self, basis):
        self.col = [_Vec3(*c) for c in basis]


class _Vec3:
    def __init__(self, x, y, z):
        self.x, self.y, self.z = x, y, z

    def __getitem__(self, i):
        return (self.x, self.y, self.z)[i]


def _close(a, b, tol=1e-6):
    return all(abs(x - y) < tol for x, y in zip(a, b))


class TestCutPlaneFromMatrix:
    def test_identity_matrix_means_z_normal_y_seam(self):
        # Identity rotation: local Z = world Z, local Y = world Y
        M = _FakeMatrix(translation=(10, 20, 30),
                        basis=[(1, 0, 0), (0, 1, 0), (0, 0, 1)])
        cp = cut_plane_from_matrix(M)
        assert cp.point == (10.0, 20.0, 30.0)
        assert cp.normal == (0.0, 0.0, 1.0)
        assert cp.seam_axis == (0.0, 1.0, 0.0)

    def test_rotated_90_around_y_means_x_normal(self):
        # 90deg around +Y: local Z -> world X, local X -> world -Z, Y unchanged
        M = _FakeMatrix(translation=(0, 0, 0),
                        basis=[(0, 0, -1), (0, 1, 0), (1, 0, 0)])
        cp = cut_plane_from_matrix(M)
        assert _close(cp.normal, (1, 0, 0))
        assert _close(cp.seam_axis, (0, 1, 0))

    def test_thickness_axis_falls_out_correctly(self):
        # For a YZ cut on a flat plate, thickness should be Z
        M = _FakeMatrix(translation=(156.7, 0, 1.5),
                        basis=[(0, 0, -1), (0, 1, 0), (1, 0, 0)])
        cp = cut_plane_from_matrix(M)
        assert _close(cp.thickness_axis, (0, 0, 1))


class TestEmptyDuckType:
    """cut_plane_from_empty is just cut_plane_from_matrix on .matrix_world.
    Sanity-check the indirection so any future regression is caught."""
    def test_reads_matrix_world(self):
        from quartermaster.blender.adapter import cut_plane_from_empty

        class FakeEmpty:
            def __init__(self, m):
                self.matrix_world = m

        M = _FakeMatrix(translation=(5, 5, 5),
                        basis=[(1, 0, 0), (0, 1, 0), (0, 0, 1)])
        cp = cut_plane_from_empty(FakeEmpty(M))
        assert cp.point == (5.0, 5.0, 5.0)
        assert cp.normal == (0.0, 0.0, 1.0)
