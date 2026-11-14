"""Step 4: flag likely tracking failures and split the path into trustworthy segments.

A failure shows up as an abrupt pose jump: a step between consecutive frames that is far
larger (in translation or rotation) than the walk's typical step. Rather than output a
silently wrong map, split the path at such jumps.
Done when: a deliberately shaken test video gets split.

Note: before scaling, translations have no unit, so thresholds must be relative
(e.g. a multiple of the median step length), not in metres.
"""

import numpy as np


def find_jumps(positions: np.ndarray, rotations_deg: np.ndarray | None = None,
               step_factor: float = 10.0) -> np.ndarray:
    """Indices i where the step i -> i+1 looks like a tracking failure."""
    raise NotImplementedError("Build plan step 4")


def split_segments(n_frames: int, jump_indices: np.ndarray) -> list[tuple[int, int]]:
    """[(start, end_exclusive), ...] segments between jumps."""
    raise NotImplementedError("Build plan step 4")
