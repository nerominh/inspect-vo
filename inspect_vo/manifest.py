"""Step 7: a manifest per run, so every result can be traced and reproduced.

manifest.json records: video hash, calibration file (and its hash), DPVO commit and
weights file (and hash), DPVO config, pipeline config, random seed, inspect-vo version,
start/end time, and status (ok / failed + error). A changed configuration produces a
separate output version instead of overwriting.
"""

from pathlib import Path


def write_manifest(run_dir: Path, **fields) -> Path:
    """Write manifest.json into run_dir and return its path."""
    raise NotImplementedError("Build plan step 7")
