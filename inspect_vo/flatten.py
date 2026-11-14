"""Step 6: project the 3D path onto the floor plane -> top-down 2D map.

Fit a plane to the camera positions; its least-variance axis (smallest singular vector)
is taken as vertical. This is valid for single-floor walks only. Project onto the plane
and write:
    map.json  - per frame: frame_index, x, y (metres), segment id
    map.png   - plot of the path
Done when: the pilot's map looks like the corridor.
"""

from pathlib import Path

import numpy as np


def floor_plane(positions: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """(centroid (3,), unit normal (3,)) of the best-fit plane."""
    raise NotImplementedError("Build plan step 6")


def project_to_2d(positions: np.ndarray) -> np.ndarray:
    """(N, 2) top-down coordinates, in the same units as the input."""
    raise NotImplementedError("Build plan step 6")


def write_map(workdir: Path, frame_indices: np.ndarray, xy: np.ndarray) -> None:
    """Write map.json and map.png."""
    raise NotImplementedError("Build plan step 6")
