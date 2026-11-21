"""Step 2: register a video and map frames to their real source timestamps.

Outputs in the video's work directory:
    video.json   - content hash (sha256), path, display/coded resolution, frame count, average fps
    frames.csv   - frame_index, source_timestamp_s (one row per frame used)

FFprobe supplies presentation timestamps from the video stream. We do not infer
timestamps from frame_index / fps: phone videos may have a variable frame rate.
"""

from __future__ import annotations

import csv
import hashlib
import json
import math
import os
import shutil
import subprocess
import tempfile
from fractions import Fraction
from pathlib import Path
from typing import Any


def _validate_video(video: Path) -> Path:
    video = Path(video)
    if not video.exists():
        raise FileNotFoundError(f"Video does not exist: {video}")
    if not video.is_file():
        raise ValueError(f"Video path is not a file: {video}")
    return video


def _validate_stride(stride: int) -> None:
    if isinstance(stride, bool) or not isinstance(stride, int) or stride < 1:
        raise ValueError(f"stride must be a positive integer, got {stride!r}")


def video_hash(video: Path, chunk_mb: int = 8) -> str:
    """Return the SHA-256 digest of a video, reading it in bounded-size chunks."""
    video = _validate_video(video)
    if isinstance(chunk_mb, bool) or not isinstance(chunk_mb, int) or chunk_mb < 1:
        raise ValueError(f"chunk_mb must be a positive integer, got {chunk_mb!r}")

    digest = hashlib.sha256()
    chunk_size = chunk_mb * 1024 * 1024
    with video.open("rb") as stream:
        for chunk in iter(lambda: stream.read(chunk_size), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _timestamp(frame: dict[str, Any], frame_index: int) -> float:
    """Read a decoded frame's presentation time without inventing a constant-FPS time."""
    value = frame.get("best_effort_timestamp_time")
    if value in (None, "N/A", ""):
        value = frame.get("pts_time")
    try:
        timestamp = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(
            f"Frame {frame_index} has no usable presentation timestamp; "
            "cannot safely map it to the source video."
        ) from exc
    if not math.isfinite(timestamp):
        raise ValueError(f"Frame {frame_index} has a non-finite timestamp: {value!r}")
    return timestamp


def _avg_fps(stream: dict[str, Any]) -> float | None:
    """Parse FFprobe's rational frame-rate metadata, preferring the average rate."""
    for key in ("avg_frame_rate", "r_frame_rate"):
        value = stream.get(key)
        if value in (None, "N/A", "", "0/0"):
            continue
        try:
            rate = float(Fraction(value))
        except (ValueError, ZeroDivisionError):
            continue
        if math.isfinite(rate) and rate > 0:
            return rate
    return None


def _rotation(stream: dict[str, Any]) -> float:
    """Read the display rotation in degrees from FFprobe stream side data.

    Older containers may expose the same value as a ``rotate`` stream tag.
    Videos without orientation metadata are treated as unrotated.
    """
    for side_data in stream.get("side_data_list") or []:
        value = side_data.get("rotation")
        if value not in (None, "N/A", ""):
            try:
                angle = float(value)
            except (TypeError, ValueError):
                continue
            if math.isfinite(angle):
                return angle
    value = (stream.get("tags") or {}).get("rotate")
    if value not in (None, "N/A", ""):
        try:
            angle = float(value)
        except (TypeError, ValueError):
            pass
        else:
            if math.isfinite(angle):
                return angle
    return 0.0


def _display_dimensions(width: int, height: int, rotation: float) -> tuple[int, int]:
    """Return the oriented dimensions commonly produced by auto-rotating video decoders."""
    quarter_turn = rotation % 180
    if math.isclose(quarter_turn, 90.0, abs_tol=1e-3):
        return height, width
    return width, height


def _rotation_warning(rotation: float) -> str | None:
    if math.isclose(rotation % 360, 0.0, abs_tol=1e-3):
        return None
    return (
        f"Video display rotation is {rotation:g} degrees. The current calibration is landscape-only; "
        "confirm the displayed orientation and use a matching calibration before running DPVO."
    )


def _probe_video(video: Path) -> tuple[dict[str, Any], list[tuple[int, float]]]:
    """Read first video stream metadata and presentation timestamps using FFprobe."""
    video = _validate_video(video)
    ffprobe = shutil.which("ffprobe")
    if ffprobe is None:
        raise RuntimeError(
            "FFprobe was not found. Install FFmpeg/FFprobe and make sure `ffprobe` is on PATH."
        )

    command = [
        ffprobe,
        "-v", "error",
        "-select_streams", "v:0",
        "-show_entries",
        "stream=width,height,nb_frames,avg_frame_rate,r_frame_rate:stream_side_data=rotation:"
        "frame=best_effort_timestamp_time,pts_time",
        "-show_frames",
        "-of", "json",
        str(video),
    ]
    try:
        result = subprocess.run(command, check=False, capture_output=True, text=True)
    except OSError as exc:
        raise RuntimeError(f"Could not start FFprobe: {exc}") from exc
    if result.returncode != 0:
        detail = result.stderr.strip() or f"exit code {result.returncode}"
        raise ValueError(f"FFprobe could not read {video}: {detail}")
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise ValueError(f"FFprobe returned invalid JSON for {video}") from exc

    streams = payload.get("streams") or []
    if not streams:
        raise ValueError(f"No video stream found in {video}")
    stream = streams[0]
    raw_frames = payload.get("frames") or []
    if not raw_frames:
        raise ValueError(f"No decodable video frames found in {video}")

    timestamps: list[tuple[int, float]] = []
    previous: float | None = None
    for frame_index, frame in enumerate(raw_frames):
        timestamp = _timestamp(frame, frame_index)
        if previous is not None and timestamp < previous:
            raise ValueError(
                f"Frame timestamps are not in presentation order at frame {frame_index}: "
                f"{timestamp} follows {previous}."
            )
        timestamps.append((frame_index, timestamp))
        previous = timestamp

    coded_width = int(stream["width"]) if stream.get("width") is not None else None
    coded_height = int(stream["height"]) if stream.get("height") is not None else None
    rotation = _rotation(stream)
    if coded_width is not None and coded_height is not None:
        display_width, display_height = _display_dimensions(coded_width, coded_height, rotation)
    else:
        display_width, display_height = coded_width, coded_height
    warning = _rotation_warning(rotation)
    metadata = {
        "path": str(video.resolve()),
        # width/height describe the displayed frames consumed by orientation-aware decoders.
        "width": display_width,
        "height": display_height,
        "coded_width": coded_width,
        "coded_height": coded_height,
        "rotation": rotation,
        "frame_count": len(timestamps),
        "avg_fps": _avg_fps(stream),
        "start_time_s": timestamps[0][1],
    }
    if warning:
        metadata["warnings"] = [warning]
    return metadata, timestamps


def frame_timestamps(video: Path, stride: int = 1) -> list[tuple[int, float]]:
    """Return original frame indices and source presentation times at the requested stride."""
    _validate_stride(stride)
    _, timestamps = _probe_video(video)
    return [item for item in timestamps if item[0] % stride == 0]


def _write_temp(path: Path, writer) -> Path:
    """Write one output beside its destination and return the temporary path."""
    handle = tempfile.NamedTemporaryFile(
        mode="w", encoding="utf-8", newline="", dir=path.parent,
        prefix=f".{path.name}.", suffix=".tmp", delete=False,
    )
    temp_path = Path(handle.name)
    try:
        with handle:
            writer(handle)
    except Exception:
        temp_path.unlink(missing_ok=True)
        raise
    return temp_path


def ingest(video: Path, workdir: Path, stride: int = 1) -> dict[str, Any]:
    """Write video.json and frames.csv into ``workdir``.

    ``frames.csv`` keeps original decoded frame indices when ``stride`` is greater
    than one. Outputs are staged before being replaced to avoid partial files on
    decoding or serialization errors.
    """
    _validate_stride(stride)
    video = _validate_video(video)
    metadata, all_timestamps = _probe_video(video)
    used_timestamps = [item for item in all_timestamps if item[0] % stride == 0]
    metadata.update({
        "sha256": video_hash(video),
        "stride": stride,
        "frames_used": len(used_timestamps),
    })

    workdir = Path(workdir)
    workdir.mkdir(parents=True, exist_ok=True)
    json_path = workdir / "video.json"
    csv_path = workdir / "frames.csv"
    temp_paths: list[Path] = []
    try:
        temp_json = _write_temp(json_path, lambda f: json.dump(metadata, f, indent=2, sort_keys=True))
        temp_paths.append(temp_json)

        def write_frames(stream) -> None:
            writer = csv.writer(stream)
            writer.writerow(["frame_index", "source_timestamp_s"])
            writer.writerows((index, f"{timestamp:.9f}") for index, timestamp in used_timestamps)

        temp_csv = _write_temp(csv_path, write_frames)
        temp_paths.append(temp_csv)
        os.replace(temp_json, json_path)
        temp_paths.remove(temp_json)
        os.replace(temp_csv, csv_path)
        temp_paths.remove(temp_csv)
    finally:
        for temp_path in temp_paths:
            temp_path.unlink(missing_ok=True)
    return metadata
