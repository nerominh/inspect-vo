"""Step 5: give the path metric scale from one known distance.

The user names two frames (camera over mark A, camera over mark B) and the real
distance between the marks. scale = real distance / estimated distance between the
two camera positions; every position is multiplied by it.
Done when: the pilot's two floor marks come out at the measured distance.
"""

import numpy as np


def scale_factor(positions: np.ndarray, frame_a: int, frame_b: int, distance_m: float) -> float:
    """Metres per unit of the unscaled DPVO path."""
    raise NotImplementedError("Build plan step 5")


def apply_scale(positions: np.ndarray, factor: float) -> np.ndarray:
    """Positions (N, 3) in metres."""
    raise NotImplementedError("Build plan step 5")
