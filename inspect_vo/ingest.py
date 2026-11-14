"""Step 2: register a video and map frames to their real source timestamps.

Outputs in the video's work directory:
    video.json   - content hash (sha256), path, resolution, frame count, nominal fps
    frames.csv   - frame_index, source_timestamp_s (one row per frame used)
Done when: both exist for the pilot video.

Why: phones often record at a variable frame rate, so frame_index / fps drifts from
real video time. Tags must point back to the exact moment in the original video.
"""

from pathlib import Path


def video_hash(video: Path, chunk_mb: int = 8) -> str:
    """sha256 of the file contents: the video's identity in manifests."""
    raise NotImplementedError("Build plan step 2")


def frame_timestamps(video: Path, stride: int = 1) -> list[tuple[int, float]]:
    """(frame_index, source timestamp in seconds) for every `stride`-th frame."""
    raise NotImplementedError("Build plan step 2")


def ingest(video: Path, workdir: Path, stride: int = 1) -> None:
    """Write video.json and frames.csv into workdir."""
    raise NotImplementedError("Build plan step 2")
