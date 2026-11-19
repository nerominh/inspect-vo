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


def test_calib_roundtrip(tmp_path):
    """write_calib then read_calib returns the same K and distortion."""
    import numpy as np

    from inspect_vo.calibrate import read_calib, write_calib
    K = np.array([[1450.25, 0, 961.5], [0, 1449.75, 538.25], [0, 0, 1]])
    dist = np.array([0.1012, -0.2534, 0.0011, -0.0007, 0.0])
    write_calib(tmp_path / "phone.txt", K, dist)
    K2, dist2 = read_calib(tmp_path / "phone.txt")
    np.testing.assert_allclose(K2, K, atol=1e-6)
    np.testing.assert_allclose(dist2, dist, atol=1e-6)
    (tmp_path / "pinhole.txt").write_text("535.4 539.2 320.1 247.6\n")   # 4 values: no distortion
    assert read_calib(tmp_path / "pinhole.txt")[1].size == 0


@pending
def test_timestamps_map_to_frames():
    """Variable-frame-rate synthetic timestamps -> each tag time maps to the right frame."""


@pending
def test_jump_splits_path():
    """A smooth path with one injected 50x step is split into two segments at that step."""
