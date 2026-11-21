"""Planned unit tests (build plan step 8). Remove the skip marker as each step is built.

Synthetic trajectories with known answers, as the proposal requires.
"""

import csv
import json
import shutil
import subprocess
from types import SimpleNamespace

import pytest

pending = pytest.mark.skip(reason="step not built yet")


@pending
def test_scale_factor_recovers_known_distance():
    """Straight line, unscaled length 2.0 between frames A and B, real 10 m -> factor 5.0."""


@pending
def test_flatten_recovers_floor_plane():
    """Points on a tilted plane + small noise -> normal recovered; 2D distances preserved."""


def test_calib_roundtrip(tmp_path):
    """write_calib then read_calib returns the same K and distortion."""
    import numpy as np

    from inspect_vo.calibrate import read_calib, write_calib
    K = np.array([[1450.25, 0, 961.5], [0, 1449.75, 538.25], [0, 0, 1]])
    dist = np.array([0.1012, -0.2534, 0.0011, -0.0007, 0.0])
    write_calib(tmp_path / "phone.txt", K, dist)
    K2, dist2 = read_calib(tmp_path / "phone.txt")
    np.testing.assert_allclose(K2, K, atol=1e-6)
    np.testing.assert_allclose(dist2, dist, atol=1e-6)
    (tmp_path / "pinhole.txt").write_text("535.4 539.2 320.1 247.6\n")   # 4 values: no distortion
    assert read_calib(tmp_path / "pinhole.txt")[1].size == 0


def test_timestamps_map_to_frames(tmp_path):
    """A VFR gap is preserved, and stride retains the source frame indices."""
    ffmpeg = shutil.which("ffmpeg")
    ffprobe = shutil.which("ffprobe")
    if ffmpeg is None or ffprobe is None:
        pytest.skip("ffmpeg and ffprobe are required to generate and inspect the VFR test clip")

    # A binary can be on PATH yet still fail to start because a shared library is missing.
    for executable in (ffmpeg, ffprobe):
        try:
            subprocess.run([executable, "-version"], check=True, capture_output=True, text=True)
        except (OSError, subprocess.CalledProcessError) as exc:
            pytest.skip(f"{executable} is installed but unusable: {exc}")
    encoders = subprocess.run(
        [ffmpeg, "-hide_banner", "-encoders"], check=True, capture_output=True, text=True
    )
    if "libx264" not in encoders.stdout:
        pytest.skip("ffmpeg was built without the libx264 encoder used by this test")

    from inspect_vo.ingest import frame_timestamps, ingest

    video = tmp_path / "vfr.mp4"
    filter_expression = "setpts='(N+if(gte(N\\,30)\\,15\\,0))/30/TB'"
    subprocess.run(
        [
            ffmpeg, "-y", "-v", "error", "-f", "lavfi", "-i",
            "testsrc2=size=320x240:rate=30", "-frames:v", "60", "-vf", filter_expression,
            "-fps_mode", "passthrough", "-c:v", "libx264", "-pix_fmt", "yuv420p", str(video),
        ],
        check=True,
        capture_output=True,
        text=True,
    )

    timestamps = frame_timestamps(video)
    assert len(timestamps) == 60
    assert timestamps[29][0] == 29 and timestamps[30][0] == 30
    assert timestamps[30][1] - timestamps[29][1] == pytest.approx(0.5333, abs=0.01)

    out = tmp_path / "ingested"
    metadata = ingest(video, out, stride=2)
    with (out / "frames.csv").open(newline="", encoding="utf-8") as stream:
        rows = list(csv.DictReader(stream))
    assert [int(row["frame_index"]) for row in rows] == list(range(0, 60, 2))
    assert float(rows[0]["source_timestamp_s"]) == pytest.approx(metadata["start_time_s"])
    saved_metadata = json.loads((out / "video.json").read_text(encoding="utf-8"))
    assert saved_metadata["avg_fps"] is not None
    assert "nominal_fps" not in saved_metadata


def test_rotation_metadata_uses_display_dimensions():
    """Orientation tags must be visible in metadata before the landscape DPVO calibration is used."""
    from inspect_vo.ingest import _display_dimensions, _rotation, _rotation_warning

    rotation = _rotation({"side_data_list": [{"side_data_type": "Display Matrix", "rotation": -90}]})
    assert rotation == -90
    assert _display_dimensions(640, 360, rotation) == (360, 640)
    assert _rotation_warning(rotation) is not None
    assert _rotation({}) == 0.0
    assert _rotation_warning(0.0) is None


def test_probe_video_saves_rotation_and_source_start_time(monkeypatch, tmp_path):
    """FFprobe's stream side data is requested and reflected in displayed metadata."""
    import inspect_vo.ingest as ingest_module

    video = tmp_path / "portrait.mp4"
    video.write_bytes(b"synthetic placeholder")
    payload = {
        "streams": [{
            "width": 640,
            "height": 360,
            "avg_frame_rate": "24/1",
            "r_frame_rate": "30/1",
            "side_data_list": [{"side_data_type": "Display Matrix", "rotation": -90}],
        }],
        "frames": [
            {"best_effort_timestamp_time": "1.500000"},
            {"best_effort_timestamp_time": "1.533333"},
        ],
    }

    def fake_run(command, **kwargs):
        entries = command[command.index("-show_entries") + 1]
        assert "stream_side_data=rotation" in entries
        return SimpleNamespace(returncode=0, stdout=json.dumps(payload), stderr="")

    monkeypatch.setattr(ingest_module.shutil, "which", lambda name: "/usr/bin/ffprobe")
    monkeypatch.setattr(ingest_module.subprocess, "run", fake_run)
    metadata, timestamps = ingest_module._probe_video(video)

    assert metadata["rotation"] == -90
    assert (metadata["coded_width"], metadata["coded_height"]) == (640, 360)
    assert (metadata["width"], metadata["height"]) == (360, 640)
    assert metadata["avg_fps"] == 24.0
    assert metadata["start_time_s"] == 1.5
    assert metadata["warnings"]
    assert timestamps[0] == (0, 1.5)


@pending
def test_jump_splits_path():
    """A smooth path with one injected 50x step is split into two segments at that step."""
