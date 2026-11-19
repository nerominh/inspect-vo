"""Calibration tests against a known camera. The end-to-end test renders a checkerboard video
through a pinhole camera WITH lens distortion, writes it as an .mp4, and checks that the tool
recovers that camera from the video alone."""
import json

import cv2
import numpy as np
import pytest

from inspect_vo import cli
from inspect_vo.calibrate import (board_points, calibrate_from_video, calibrate_points, detect, make_board,
                                  read_calib, run, scale_intrinsics, select_views)

W, H = 1280, 720
K_TRUE = np.array([[900.0, 0, 642.0], [0, 900.0, 358.0], [0, 0, 1]])
DIST_TRUE = np.array([-0.12, 0.05, 0.0005, -0.0003, 0.0])   # mild barrel distortion, like a phone main lens
PATTERN = (9, 6)
SQUARE_M = 0.025


def random_poses(n, rng):
    """Board poses 0.45-0.9 m away, tilted up to ~35 degrees, spread over the image."""
    obj = board_points(PATTERN, SQUARE_M * 1000)
    centre = obj.mean(axis=0)
    poses = []
    while len(poses) < n:
        rvec = rng.uniform(-0.6, 0.6, 3) * np.array([1, 1, 0.5])
        z = rng.uniform(0.45, 0.9)
        x, y = rng.uniform(-0.28, 0.28) * z, rng.uniform(-0.16, 0.16) * z
        R, _ = cv2.Rodrigues(rvec)
        tvec = np.array([x, y, z]) - R @ centre
        img, _ = cv2.projectPoints(obj, rvec, tvec, K_TRUE, DIST_TRUE)
        img = img.reshape(-1, 2)
        if img[:, 0].min() > 15 and img[:, 0].max() < W - 15 and img[:, 1].min() > 15 and img[:, 1].max() < H - 15:
            poses.append((rvec, tvec))
    return poses


def render_video(path, n=60, seed=0):
    rng = np.random.default_rng(seed)
    px, margin = 40, 40
    board = np.full(((PATTERN[1] + 1) * px + 2 * margin, (PATTERN[0] + 1) * px + 2 * margin), 255, np.uint8)
    for r in range(PATTERN[1] + 1):
        for c in range(PATTERN[0] + 1):
            if (r + c) % 2 == 0:
                board[margin + r * px:margin + (r + 1) * px, margin + c * px:margin + (c + 1) * px] = 0
    # board pixel -> board metres (origin at the first INNER corner, matching board_points)
    s = SQUARE_M / px
    A = np.array([[s, 0, -(margin + px) * s], [0, s, -(margin + px) * s], [0, 0, 1]])
    # distortion via remap: for every distorted output pixel, where is it in the undistorted image?
    grid = np.stack(np.meshgrid(np.arange(W), np.arange(H)), -1).reshape(-1, 1, 2).astype(np.float32)
    und = cv2.undistortPoints(grid, K_TRUE, DIST_TRUE, P=K_TRUE).reshape(H, W, 2)
    map_x, map_y = und[..., 0].astype(np.float32), und[..., 1].astype(np.float32)
    vw = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"mp4v"), 30, (W, H))
    assert vw.isOpened(), "OpenCV cannot write mp4 here"
    for rvec, tvec in random_poses(n, rng):
        R, _ = cv2.Rodrigues(rvec)
        Hm = K_TRUE @ np.column_stack([R[:, 0], R[:, 1], tvec]) @ A
        flat = cv2.warpPerspective(board, Hm, (W, H), flags=cv2.INTER_LINEAR, borderValue=170)
        img = cv2.remap(flat, map_x, map_y, cv2.INTER_LINEAR, borderValue=170)
        vw.write(cv2.cvtColor(img, cv2.COLOR_GRAY2BGR))
    vw.release()


def test_printed_board_is_detectable(tmp_path):
    out = make_board(tmp_path / "board.png")
    img = cv2.imread(str(out), cv2.IMREAD_GRAYSCALE)
    corners = detect(img, PATTERN)
    assert corners is not None and corners.shape[0] == 54


def test_recovers_known_camera_from_points():
    rng = np.random.default_rng(1)
    obj = board_points(PATTERN, 25.0)
    obj_pts, img_pts = [], []
    for rvec, tvec in random_poses(30, rng):
        p, _ = cv2.projectPoints(obj, rvec, tvec, K_TRUE, DIST_TRUE)
        img_pts.append((p + rng.normal(0, 0.2, p.shape)).astype(np.float32))   # 0.2 px corner noise
        obj_pts.append(obj)
    res = calibrate_points(obj_pts, img_pts, (W, H))
    assert res.K[0][0] == pytest.approx(900.0, rel=0.005)
    assert res.K[0][2] == pytest.approx(642.0, abs=3)
    assert res.dist[0] == pytest.approx(-0.12, abs=0.01)
    assert res.rms_px < 0.35


def test_too_few_views_is_refused():
    obj = board_points(PATTERN, 25.0)
    with pytest.raises(ValueError, match="at least 8"):
        calibrate_points([obj] * 3, [np.zeros((54, 1, 2), np.float32)] * 3, (W, H))


def test_view_selection_prefers_new_coverage():
    a = {"cells": {(0, 0), (1, 0)}, "scale": 0.1, "tilt": 0.0, "sharpness": 100}
    same = {"cells": {(0, 0), (1, 0)}, "scale": 0.1, "tilt": 0.0, "sharpness": 900}
    new = {"cells": {(6, 5), (7, 5)}, "scale": 0.1, "tilt": 0.0, "sharpness": 100}
    chosen = select_views([a, same, new], (W, H), max_views=2)
    assert new in chosen


def test_scale_intrinsics_for_resized_frames():
    assert scale_intrinsics(1500, 1500, 960, 540, 0.5) == (750, 750, 480, 270)


def test_end_to_end_video(tmp_path):
    video = tmp_path / "calib.mp4"
    render_video(video)
    out = tmp_path / "calib" / "synthetic.txt"
    res = run(video, out, 25.0, (9, 6), every=1, max_views=40, min_sharp=10.0)
    assert res.K[0][0] == pytest.approx(900.0, rel=0.015)
    assert res.K[1][1] == pytest.approx(900.0, rel=0.015)
    assert res.dist[0] == pytest.approx(-0.12, abs=0.03)
    assert res.dist[1] == pytest.approx(0.05, abs=0.03)
    assert res.dist[4] == 0.0                     # k3 fixed by default
    assert res.rms_px < 1.0                       # video compression adds corner noise
    assert res.edges_ok
    # What matters for DPVO: how far off undistortion is anywhere in the frame, corners included.
    g = np.stack(np.meshgrid(np.linspace(0, W - 1, 64), np.linspace(0, H - 1, 36)), -1)
    g = g.reshape(-1, 1, 2).astype(np.float32)
    truth = cv2.undistortPoints(g, K_TRUE, DIST_TRUE, P=K_TRUE).reshape(-1, 2)
    est = cv2.undistortPoints(g, np.array(res.K), np.array(res.dist), P=K_TRUE).reshape(-1, 2)
    assert np.linalg.norm(est - truth, axis=1).max() < 10.0
    line = out.read_text().split()
    assert len(line) == 9                         # fx fy cx cy k1 k2 p1 p2 k3, the DPVO calib format
    K, dist = read_calib(out)
    assert K[0, 0] == pytest.approx(res.K[0][0], abs=1e-4) and dist.shape == (5,)
    rec = json.loads(out.with_suffix(".json").read_text())
    assert rec["image_size"] == [W, H] and len(rec["video"]["sha256"]) == 64
    assert (tmp_path / "calib" / "synthetic_check.jpg").exists()


def test_free_k3_extrapolation_is_flagged(tmp_path):
    """With corners covering only part of the frame, a free k3 fits the data but folds back near the
    image corners (hundreds of px off). The tool must flag that rather than hand it to DPVO."""
    video = tmp_path / "calib.mp4"
    render_video(video)
    res = run(video, tmp_path / "c" / "freek3.txt", 25.0, (9, 6), every=1, max_views=40, min_sharp=10.0,
              free_k3=True)
    assert not res.edges_ok and res.quality == "poor"


def test_planned_interface_calibrate_from_video(tmp_path):
    """The function the skeleton planned: (K, dist, rms) straight from a video."""
    video = tmp_path / "calib.mp4"
    render_video(video)
    K, dist, rms = calibrate_from_video(video, 25.0, (9, 6), max_frames=30)
    assert K.shape == (3, 3) and dist.shape == (5,)
    assert K[0, 0] == pytest.approx(900.0, rel=0.02) and rms < 1.0


def test_cli_calibrate_and_board(tmp_path, capsys):
    video = tmp_path / "calib.mp4"
    render_video(video)
    out = tmp_path / "calib" / "test_phone_720p_30.txt"
    assert cli.main(["calibrate", str(video), "--square-mm", "25", "--out", str(out), "--every", "1"]) == 0
    assert out.exists() and "QUALITY:" in capsys.readouterr().out
    assert cli.main(["board", "--out", str(tmp_path / "board.png")]) == 0
    assert (tmp_path / "board.png").exists()
