"""Step 3: run DPVO on an ingested video. The ONLY module that imports DPVO.

Feeds the frames listed in frames.csv (undistorted with our calibration) to
`dpvo.dpvo.DPVO`, the same way DPVO's demo.py / evaluate_tum.py do, and writes:
    runs/run_XX/trajectory.tum   - timestamp tx ty tz qx qy qz qw (TUM format, no metric scale)
    runs/run_XX/points.ply       - sparse point cloud (optional)
Done when: a trajectory file exists for the pilot video.

DPVO is not deterministic (random patch selection): run it several times (default 5).
"""

from pathlib import Path


def run_dpvo(workdir: Path, calib: Path, network: Path, dpvo_config: Path,
             run_index: int = 0, seed: int | None = None) -> Path:
    """One DPVO run over the ingested frames. Returns the trajectory file path."""
    raise NotImplementedError("Build plan step 3")
