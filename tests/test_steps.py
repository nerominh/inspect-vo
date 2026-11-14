"""Planned unit tests (build plan step 8). Remove the skip marker as each step is built.

Synthetic trajectories with known answers, as the proposal requires.
"""

import pytest

pending = pytest.mark.skip(reason="step not built yet")


@pending
def test_scale_factor_recovers_known_distance():
    """Straight line, unscaled length 2.0 between frames A and B, real 10 m -> factor 5.0."""


@pending
def test_flatten_recovers_floor_plane():
    """Points on a tilted plane + small noise -> normal recovered; 2D distances preserved."""


@pending
def test_calib_roundtrip():
    """write_calib then read_calib returns the same K and distortion."""


@pending
def test_timestamps_map_to_frames():
    """Variable-frame-rate synthetic timestamps -> each tag time maps to the right frame."""


@pending
def test_jump_splits_path():
    """A smooth path with one injected 50x step is split into two segments at that step."""
