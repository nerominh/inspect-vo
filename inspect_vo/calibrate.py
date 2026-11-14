"""Step 1: camera calibration from a checkerboard video (once per phone).

Output: a one-line text file in DPVO's calib format
    fx fy cx cy k1 k2 p1 p2 k3
(pixels, for the full-resolution video frames), plus the RMS reprojection error.
Done when: the file exists and the reprojection error is under ~0.5 px.

Record the checkerboard in the SAME camera mode as the walkthroughs
(resolution, fps, lens, stabilisation), because video mode crops the sensor.
"""

from pathlib import Path

import numpy as np


def calibrate_from_video(video: Path, square_mm: float, pattern: tuple[int, int] = (9, 6),
                         max_frames: int = 60) -> tuple[np.ndarray, np.ndarray, float]:
    """Detect checkerboard corners in sampled frames and run cv2.calibrateCamera.

    Returns (K 3x3, dist (5,), rms reprojection error in px).
    """
    raise NotImplementedError("Build plan step 1")


def write_calib(path: Path, K: np.ndarray, dist: np.ndarray) -> None:
    """Write `fx fy cx cy k1 k2 p1 p2 k3` on one line (DPVO calib format)."""
    raise NotImplementedError("Build plan step 1")


def read_calib(path: Path) -> tuple[np.ndarray, np.ndarray]:
    """Read a DPVO calib file -> (K 3x3, dist). dist is empty if the file has only 4 values."""
    raise NotImplementedError("Build plan step 1")
