"""Step 1: camera calibration from a checkerboard video (once per phone).

Output: a one-line text file in DPVO's calib format
    fx fy cx cy k1 k2 p1 p2 k3
(pixels, for the full-resolution video frames), plus a JSON record next to it
(reprojection error, coverage, image size, video sha256, notes) and a check image.
Done when: the file exists and the reprojection error is under ~0.5 px.

Record the checkerboard in the SAME camera mode as the walkthroughs
(resolution, fps, lens, stabilisation), because video mode crops the sensor.
How to film it and which phone settings to use: docs/CALIBRATION.md.

Needs only numpy + OpenCV (no GPU, no DPVO).
"""

from __future__ import annotations

import hashlib
import json
import platform
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path

import cv2
import numpy as np


# Quality thresholds for the reprojection error (pixels, at the calibrated resolution).
RMS_GOOD = 0.5
RMS_OK = 1.0
COVERAGE_GRID = (8, 6)      # image split into 8 x 6 cells to measure where corners were seen
COVERAGE_MIN = 0.70         # want corners in at least 70% of cells, incl. edges, to pin down distortion


# ----------------------------------------------------------------------------------------- board
def make_board(out: Path, cols: int = 9, rows: int = 6, square_mm: float = 25.0, dpi: int = 300) -> Path:
    """Write a printable checkerboard with `cols` x `rows` INNER corners (so cols+1 x rows+1 squares).

    The default 10 x 7 squares of 25 mm = 250 x 175 mm fits on A4 landscape with a white margin,
    which the detector needs.
    """
    px = int(round(square_mm / 25.4 * dpi))
    margin = px
    w, h = (cols + 1) * px + 2 * margin, (rows + 1) * px + 2 * margin
    img = np.full((h, w), 255, np.uint8)
    for r in range(rows + 1):
        for c in range(cols + 1):
            if (r + c) % 2 == 0:
                y, x = margin + r * px, margin + c * px
                img[y:y + px, x:x + px] = 0
    label = f"{cols}x{rows} inner corners, {square_mm} mm squares - print at 100% / actual size"
    cv2.putText(img, label, (margin, h - margin // 3), cv2.FONT_HERSHEY_SIMPLEX, px / 120, 0, max(1, px // 60))
    out.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(out), img)
    return out


# ------------------------------------------------------------------------------------- detection
def sharpness(gray: np.ndarray) -> float:
    """Variance of the Laplacian: low values mean motion blur or defocus."""
    return float(cv2.Laplacian(gray, cv2.CV_64F).var())


def detect(gray: np.ndarray, pattern: tuple[int, int]) -> np.ndarray | None:
    """Return Nx1x2 float32 corner positions, or None if the full board is not found."""
    if hasattr(cv2, "findChessboardCornersSB"):
        ok, corners = cv2.findChessboardCornersSB(gray, pattern, flags=cv2.CALIB_CB_NORMALIZE_IMAGE)
        if ok:
            return corners.astype(np.float32)
    ok, corners = cv2.findChessboardCorners(
        gray, pattern, flags=cv2.CALIB_CB_ADAPTIVE_THRESH | cv2.CALIB_CB_NORMALIZE_IMAGE)
    if not ok:
        return None
    crit = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 30, 1e-3)
    return cv2.cornerSubPix(gray, corners, (11, 11), (-1, -1), crit).astype(np.float32)


def board_points(pattern: tuple[int, int], square_mm: float) -> np.ndarray:
    """3D corner positions on the board plane (z = 0), in metres."""
    cols, rows = pattern
    obj = np.zeros((cols * rows, 3), np.float32)
    obj[:, :2] = np.mgrid[0:cols, 0:rows].T.reshape(-1, 2) * (square_mm / 1000.0)
    return obj


def cells_covered(corners: np.ndarray, size: tuple[int, int], grid=COVERAGE_GRID) -> set[tuple[int, int]]:
    w, h = size
    pts = corners.reshape(-1, 2)
    gx = np.clip((pts[:, 0] / w * grid[0]).astype(int), 0, grid[0] - 1)
    gy = np.clip((pts[:, 1] / h * grid[1]).astype(int), 0, grid[1] - 1)
    return set(zip(gx.tolist(), gy.tolist(), strict=True))


def select_views(views: list[dict], size: tuple[int, int], max_views: int = 40) -> list[dict]:
    """Greedy pick: each new view should cover image cells not seen yet, and differ in apparent
    board size (distance) and tilt. Many near-identical frames add time, not information."""
    remaining = list(views)
    chosen: list[dict] = []
    covered: set[tuple[int, int]] = set()
    while remaining and len(chosen) < max_views:
        def score(v: dict, covered: set = covered) -> float:
            new_cells = len(v["cells"] - covered)
            novelty = min((abs(v["scale"] - c["scale"]) + abs(v["tilt"] - c["tilt"]) for c in chosen), default=1.0)
            return new_cells + 5.0 * novelty + 1e-6 * v["sharpness"]
        best = max(remaining, key=score)
        chosen.append(best)
        covered |= best["cells"]
        remaining.remove(best)
    return chosen


def view_descriptor(corners: np.ndarray, pattern: tuple[int, int], size: tuple[int, int]) -> tuple[float, float]:
    """Cheap pose proxies: board area relative to the image (distance) and the ratio of opposite
    edge lengths (tilt)."""
    cols, rows = pattern
    p = corners.reshape(rows, cols, 2)
    quad = np.array([p[0, 0], p[0, -1], p[-1, -1], p[-1, 0]], np.float32)
    area = abs(cv2.contourArea(quad)) / (size[0] * size[1])
    top, bottom = np.linalg.norm(quad[1] - quad[0]), np.linalg.norm(quad[2] - quad[3])
    left, right = np.linalg.norm(quad[3] - quad[0]), np.linalg.norm(quad[2] - quad[1])
    tilt = abs(np.log(top / bottom)) + abs(np.log(left / right))
    return float(area), float(tilt)


# ----------------------------------------------------------------------------------- calibration
@dataclass
class CalibResult:
    image_size: tuple[int, int]          # (width, height)
    K: list[list[float]]
    dist: list[float]                    # k1 k2 p1 p2 k3
    rms_px: float
    per_view_rms_px: list[float]
    views_used: int
    views_dropped_as_outliers: int
    coverage: float
    fov_deg: tuple[float, float]
    notes: list[str] = field(default_factory=list)
    edges_ok: bool = True

    @property
    def quality(self) -> str:
        if not self.edges_ok:
            return "poor"
        if self.rms_px <= RMS_GOOD and self.coverage >= COVERAGE_MIN:
            return "good"
        if self.rms_px <= RMS_OK:
            return "usable"
        return "poor"

    def dpvo_line(self) -> str:
        fx, fy, cx, cy = self.K[0][0], self.K[1][1], self.K[0][2], self.K[1][2]
        return " ".join(f"{v:.6f}" for v in [fx, fy, cx, cy, *self.dist])


def _per_view_rms(obj, img, rvecs, tvecs, K, dist) -> list[float]:
    errs = []
    for o, i, r, t in zip(obj, img, rvecs, tvecs, strict=True):
        proj, _ = cv2.projectPoints(o, r, t, K, dist)
        errs.append(float(np.sqrt(np.mean(np.sum((proj.reshape(-1, 2) - i.reshape(-1, 2)) ** 2, axis=1)))))
    return errs


def edges_are_sane(K: np.ndarray, dist: np.ndarray, size: tuple[int, int], max_stretch: float = 1.4) -> bool:
    """True if the radial lens model stays physical out to the farthest image corner.

    In normalised coordinates the model maps an ideal radius r to r_d = r(1 + k1 r^2 + k2 r^4 + k3 r^6).
    That curve must keep increasing until it reaches the corner's radius, and must get there without
    an implausible stretch (r / r_d > max_stretch). A fitted polynomial can fold back or blow up where
    no corners were observed, which would warp exactly the image edges DPVO tracks."""
    k1, k2, k3 = float(dist.ravel()[0]), float(dist.ravel()[1]), float(dist.ravel()[4]) if dist.size > 4 else 0.0
    w, h = size
    fx, fy, cx, cy = K[0, 0], K[1, 1], K[0, 2], K[1, 2]
    rc = max(np.hypot((x - cx) / fx, (y - cy) / fy) for x in (0, w - 1) for y in (0, h - 1))
    r = np.linspace(0, max_stretch * rc, 4000)
    rd = r * (1 + k1 * r**2 + k2 * r**4 + k3 * r**6)
    reach = np.nonzero(rd >= rc)[0]
    if reach.size == 0:                      # never reaches the corner within the allowed stretch
        return False
    upto = reach[0]
    return bool(np.all(np.diff(rd[:upto + 1]) > 0))


def calibrate_points(obj_pts: list[np.ndarray], img_pts: list[np.ndarray], size: tuple[int, int],
                     free_k3: bool = False) -> CalibResult:
    """Pinhole + distortion (k1 k2 p1 p2, and k3 only if free_k3), with one round of outlier-view
    rejection. k3 is fixed at 0 by default: for a phone's normal (non-wide) lens it adds nothing but
    trades off against k2 and can make undistortion explode near the image corners."""
    if len(img_pts) < 8:
        raise ValueError(f"Only {len(img_pts)} usable views; need at least 8 (aim for 20-40).")
    flags = 0 if free_k3 else cv2.CALIB_FIX_K3
    rms, K, dist, rvecs, tvecs = cv2.calibrateCamera(obj_pts, img_pts, size, None, None, flags=flags)
    errs = _per_view_rms(obj_pts, img_pts, rvecs, tvecs, K, dist)
    med = float(np.median(errs))
    keep = [i for i, e in enumerate(errs) if e <= max(2.0 * med, 0.3)]
    dropped = len(errs) - len(keep)
    if dropped and len(keep) >= 8:
        obj_pts = [obj_pts[i] for i in keep]
        img_pts = [img_pts[i] for i in keep]
        rms, K, dist, rvecs, tvecs = cv2.calibrateCamera(obj_pts, img_pts, size, None, None, flags=flags)
        errs = _per_view_rms(obj_pts, img_pts, rvecs, tvecs, K, dist)
    else:
        dropped = 0

    covered: set = set()
    for i in img_pts:
        covered |= cells_covered(i, size)
    coverage = len(covered) / (COVERAGE_GRID[0] * COVERAGE_GRID[1])
    w, h = size
    fov = (float(np.degrees(2 * np.arctan(w / (2 * K[0, 0])))), float(np.degrees(2 * np.arctan(h / (2 * K[1, 1])))))

    notes = []
    edges_ok = edges_are_sane(K, dist, size)
    if not edges_ok:
        notes.append("Distortion model misbehaves near the image corners (fitted curve folds back). Do not use "
                     "this calibration: film again with the board reaching all edges and corners.")
    if coverage < COVERAGE_MIN:
        notes.append(f"Corners reached only {coverage:.0%} of the image. Film again moving the board into "
                     "all corners and edges of the frame; distortion is poorly measured otherwise.")
    if abs(K[0, 2] - w / 2) > 0.1 * w or abs(K[1, 2] - h / 2) > 0.1 * h:
        notes.append("Principal point is far from the image centre: check the result, often a sign of too "
                     "few tilted views.")
    if abs(K[0, 0] / K[1, 1] - 1) > 0.02:
        notes.append("fx and fy differ by more than 2%: unusual for a phone; often too few views.")
    return CalibResult((w, h), K.tolist(), dist.ravel()[:5].tolist(), float(rms), errs, len(img_pts),
                       dropped, coverage, fov, notes, edges_ok)


def scale_intrinsics(fx: float, fy: float, cx: float, cy: float, factor: float) -> tuple[float, ...]:
    """Intrinsics for frames resized by `factor` (e.g. 0.5 for 1920x1080 -> 960x540).
    Distortion coefficients are unitless and stay the same."""
    return fx * factor, fy * factor, cx * factor, cy * factor


# ------------------------------------------------------------------------------------------- run
def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def collect_views(video: Path, pattern: tuple[int, int], square_mm: float, every: int, min_sharp: float,
                  log=print) -> tuple[list[dict], tuple[int, int], dict]:
    cap = cv2.VideoCapture(str(video))
    if not cap.isOpened():
        raise SystemExit(f"Cannot open {video}. If it is HEVC/HDR, re-record with H.264 ('Most Compatible').")
    info = {"fps": cap.get(cv2.CAP_PROP_FPS), "frames": int(cap.get(cv2.CAP_PROP_FRAME_COUNT))}
    obj = board_points(pattern, square_mm)
    views, size, idx, tried, blurry = [], None, 0, 0, 0
    while True:
        ok, frame = cap.read()
        if not ok:
            break
        if idx % every == 0:
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            if size is None:
                size = (gray.shape[1], gray.shape[0])
            elif (gray.shape[1], gray.shape[0]) != size:
                raise SystemExit("Frame size changed inside the video; record at one fixed resolution.")
            tried += 1
            s = sharpness(gray)
            if s < min_sharp:
                blurry += 1
            else:
                corners = detect(gray, pattern)
                if corners is not None:
                    area, tilt = view_descriptor(corners, pattern, size)
                    views.append({"frame": idx, "corners": corners, "obj": obj, "sharpness": s,
                                  "cells": cells_covered(corners, size), "scale": area, "tilt": tilt})
        idx += 1
    cap.release()
    if size is None:
        raise SystemExit(f"No frames could be read from {video}.")
    info.update(sampled=tried, too_blurry=blurry, board_found=len(views))
    log(f"Read {idx} frames at {size[0]}x{size[1]}; checked {tried}, {blurry} too blurry, "
        f"board found in {len(views)}.")
    return views, size, info


def write_check_image(video: Path, frame_idx: int, corners: np.ndarray, pattern, res: CalibResult, out: Path):
    cap = cv2.VideoCapture(str(video))
    cap.set(cv2.CAP_PROP_POS_FRAMES, frame_idx)
    ok, frame = cap.read()
    cap.release()
    if not ok:
        return
    left = frame.copy()
    cv2.drawChessboardCorners(left, pattern, corners, True)
    right = cv2.undistort(frame, np.array(res.K), np.array(res.dist))
    both = np.hstack([left, right])
    cv2.putText(both, "detected corners", (20, 50), cv2.FONT_HERSHEY_SIMPLEX, 1.5, (0, 255, 0), 3)
    cv2.putText(both, "undistorted: board edges should be straight", (left.shape[1] + 20, 50),
                cv2.FONT_HERSHEY_SIMPLEX, 1.5, (0, 255, 0), 3)
    scale = 1600 / both.shape[1]
    cv2.imwrite(str(out), cv2.resize(both, None, fx=scale, fy=scale), [cv2.IMWRITE_JPEG_QUALITY, 85])


def run(video: Path, out: Path, square_mm: float, pattern: tuple[int, int] = (9, 6), every: int = 5,
        max_views: int = 40, min_sharp: float = 50.0, notes: str = "", free_k3: bool = False) -> CalibResult:
    """Full step 1: write `out` (DPVO calib line), `out` with .json (record) and <stem>_check.jpg."""
    views, size, info = collect_views(video, pattern, square_mm, every, min_sharp)
    chosen = select_views(views, size, max_views)
    print(f"Using {len(chosen)} diverse views for calibration.")
    res = calibrate_points([v["obj"] for v in chosen], [v["corners"] for v in chosen], size, free_k3)

    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    write_calib(out, np.array(res.K), np.array(res.dist))
    record = {
        "calib_file": out.name, "created": datetime.now().isoformat(timespec="seconds"),
        "quality": res.quality, **asdict(res),
        "board": {"inner_corners": list(pattern), "square_mm": square_mm},
        "video": {"file": Path(video).name, "sha256": sha256(Path(video)), **info},
        "settings": {"every_nth_frame": every, "max_views": max_views, "min_sharpness": min_sharp,
                     "free_k3": free_k3},
        "opencv": cv2.__version__, "host": platform.node(), "notes": notes,
    }
    out.with_suffix(".json").write_text(json.dumps(record, indent=2))
    best = max(chosen, key=lambda v: v["sharpness"])
    write_check_image(Path(video), best["frame"], best["corners"], pattern, res,
                      out.with_name(out.stem + "_check.jpg"))

    fx, fy, cx, cy = res.K[0][0], res.K[1][1], res.K[0][2], res.K[1][2]
    print(f"\nfx={fx:.1f} fy={fy:.1f} cx={cx:.1f} cy={cy:.1f}  dist={np.round(res.dist, 4).tolist()}")
    print(f"Field of view {res.fov_deg[0]:.1f} x {res.fov_deg[1]:.1f} deg")
    print(f"Reprojection error {res.rms_px:.3f} px (good <= {RMS_GOOD}, usable <= {RMS_OK}); "
          f"coverage {res.coverage:.0%}; {res.views_dropped_as_outliers} outlier views dropped")
    print(f"QUALITY: {res.quality.upper()}")
    for n in res.notes:
        print(f"  NOTE: {n}")
    print(f"\nWrote {out}, {out.with_suffix('.json').name} and {out.stem}_check.jpg")
    return res


# ------------------------------------------------------------------ the stub's planned interface
def calibrate_from_video(video: Path, square_mm: float, pattern: tuple[int, int] = (9, 6),
                         max_frames: int = 60) -> tuple[np.ndarray, np.ndarray, float]:
    """Detect checkerboard corners in sampled frames and run cv2.calibrateCamera.

    `max_frames` is the most views used for the fit (the most diverse ones are picked).
    Returns (K 3x3, dist (5,), rms reprojection error in px). k3 is fixed at 0 (see calibrate_points).
    """
    views, size, _ = collect_views(Path(video), pattern, square_mm, every=5, min_sharp=50.0)
    chosen = select_views(views, size, max_frames)
    res = calibrate_points([v["obj"] for v in chosen], [v["corners"] for v in chosen], size)
    return np.array(res.K), np.array(res.dist), res.rms_px


def write_calib(path: Path, K: np.ndarray, dist: np.ndarray) -> None:
    """Write `fx fy cx cy k1 k2 p1 p2 k3` on one line (DPVO calib format)."""
    K = np.asarray(K, dtype=float)
    vals = [K[0, 0], K[1, 1], K[0, 2], K[1, 2], *np.asarray(dist, dtype=float).ravel()[:5]]
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(" ".join(f"{v:.6f}" for v in vals) + "\n")


def read_calib(path: Path) -> tuple[np.ndarray, np.ndarray]:
    """Read a DPVO calib file -> (K 3x3, dist). dist is empty if the file has only 4 values."""
    vals = np.loadtxt(path, dtype=float).ravel()
    if vals.size < 4:
        raise ValueError(f"{path}: expected at least 4 values (fx fy cx cy), got {vals.size}")
    fx, fy, cx, cy = vals[:4]
    K = np.array([[fx, 0.0, cx], [0.0, fy, cy], [0.0, 0.0, 1.0]])
    return K, vals[4:].copy()
