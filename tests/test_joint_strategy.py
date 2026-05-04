import pytest
from quartermaster.joint_strategy import (
    pick_joint,
    viable_joints,
    JointType,
    JointSpec,
    MIN_THICKNESS_MM,
)


class TestThinStock:
    """Below 3mm, only scarf is mechanically viable."""

    def test_very_thin_picks_scarf_12_to_1(self):
        spec = pick_joint(thickness=1.5, seam_length=200)
        assert spec.joint == JointType.SCARF
        assert spec.params["ratio"] == 12

    def test_2mm_picks_scarf(self):
        spec = pick_joint(thickness=2.0, seam_length=150)
        assert spec.joint == JointType.SCARF


class TestSweetSpot3to5mm:
    """User's primary working range — covers the 2-axis matrix."""

    def test_short_seam_picks_dovetail(self):
        spec = pick_joint(thickness=4.0, seam_length=60)
        assert spec.joint == JointType.DOVETAIL

    def test_medium_seam_picks_scarf(self):
        spec = pick_joint(thickness=4.0, seam_length=215)
        assert spec.joint == JointType.SCARF
        assert spec.params["ratio"] == 8

    def test_medium_seam_includes_alignment_pins(self):
        spec = pick_joint(thickness=4.0, seam_length=215)
        assert spec.pin_count >= 2

    def test_long_seam_picks_finger(self):
        spec = pick_joint(thickness=4.0, seam_length=500)
        assert spec.joint == JointType.FINGER


class TestMidThickness5to8mm:
    def test_short_seam_picks_dovetail(self):
        spec = pick_joint(thickness=6.0, seam_length=80)
        assert spec.joint == JointType.DOVETAIL

    def test_long_seam_picks_finger(self):
        spec = pick_joint(thickness=6.0, seam_length=400)
        assert spec.joint == JointType.FINGER


class TestThickStock:
    def test_thick_long_picks_sliding_dovetail(self):
        spec = pick_joint(thickness=12.0, seam_length=400)
        assert spec.joint == JointType.SLIDING_DOVETAIL

    def test_thick_short_picks_box(self):
        spec = pick_joint(thickness=12.0, seam_length=60)
        assert spec.joint == JointType.BOX


class TestOptionsExpandWithThickness:
    """The user's principle: as Z grows, more joint types become viable.
    The viable set must grow monotonically."""

    def test_viable_set_grows_monotonically(self):
        thicknesses = [1.0, 3.0, 5.0, 8.0, 12.0]
        sets = [viable_joints(t) for t in thicknesses]
        for prev, nxt in zip(sets, sets[1:]):
            assert prev.issubset(nxt), f"viable set shrank: {prev} -> {nxt}"

    def test_thicker_unlocks_strictly_more(self):
        assert len(viable_joints(1.0)) < len(viable_joints(12.0))

    def test_each_threshold_unlocks_at_least_one_joint(self):
        # Crossing 3, 5, 8 mm should each unlock something new.
        assert viable_joints(2.99) != viable_joints(3.0)
        assert viable_joints(4.99) != viable_joints(5.0)
        assert viable_joints(7.99) != viable_joints(8.0)


class TestSeamVisibility:
    def test_visible_seam_picks_scarf_when_otherwise_finger(self):
        # Without flag: 6mm × 300mm picks finger.
        # With flag: scarf for optical blending.
        normal = pick_joint(thickness=6.0, seam_length=300)
        visible = pick_joint(thickness=6.0, seam_length=300, seam_visible=True)
        assert normal.joint == JointType.FINGER
        assert visible.joint == JointType.SCARF


class TestManualOverride:
    """Escape hatch for when the auto-pick is wrong for the user's situation."""

    def test_override_returns_requested_joint(self):
        spec = pick_joint(thickness=4.0, seam_length=215, override=JointType.HALF_LAP)
        assert spec.joint == JointType.HALF_LAP
        assert "override" in spec.rationale.lower()

    def test_override_blocks_unviable_joint(self):
        with pytest.raises(ValueError, match="not viable"):
            pick_joint(thickness=1.5, seam_length=200, override=JointType.DOVETAIL)


class TestSerialization:
    """JointSpec must round-trip through dict so configs save/tune cleanly."""

    def test_spec_round_trips(self):
        spec = pick_joint(thickness=4.0, seam_length=215)
        rebuilt = JointSpec.from_dict(spec.to_dict())
        assert rebuilt == spec

    def test_dict_form_is_json_safe(self):
        import json
        spec = pick_joint(thickness=4.0, seam_length=215)
        json.dumps(spec.to_dict())  # must not raise


class TestEdgeCases:
    def test_zero_thickness_raises(self):
        with pytest.raises(ValueError):
            pick_joint(thickness=0.0, seam_length=100)

    def test_negative_thickness_raises(self):
        with pytest.raises(ValueError):
            pick_joint(thickness=-1.0, seam_length=100)

    def test_negative_seam_length_raises(self):
        with pytest.raises(ValueError):
            pick_joint(thickness=3.0, seam_length=-1.0)


class TestReferenceBuild:
    """The Sketch.003 case that motivated the whole project."""

    def test_sketch_003_picks_scarf_8_1_with_pins(self):
        spec = pick_joint(thickness=3.0, seam_length=215)
        assert spec.joint == JointType.SCARF
        assert spec.params["ratio"] == 8
        assert spec.params["overlap_mm"] == pytest.approx(24.0)
        assert spec.pin_count == 2
