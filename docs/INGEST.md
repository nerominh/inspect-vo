# Video ingest

Step 2 registers a video before trajectory estimation. It records the file's SHA-256 and maps each processed frame back to its original frame index and source presentation timestamp. This mapping is necessary for tags to point to the correct video time, particularly for variable-frame-rate phone videos.

## Run it

From the repository root in the DPVO Python environment:

```bash
inspect-vo ingest ~/data/pilot/corridor.mp4 --out outputs/corridor
```

To record every second frame while retaining its original index:

```bash
inspect-vo ingest ~/data/pilot/corridor.mp4 --out outputs/corridor --stride 2
```

The command requires `ffprobe` (provided by FFmpeg) on `PATH`. In WSL Ubuntu, install it with `sudo apt install ffmpeg`; in the `dpvo` Conda environment, use `conda install -c conda-forge ffmpeg`. It reads per-frame presentation timestamps and does not synthesize them by dividing the frame index by an average FPS. Frames with missing, non-finite, or out-of-order timestamps are rejected with an error.

## Outputs

`video.json` records the resolved source path, SHA-256, displayed dimensions (`width`, `height`), coded dimensions, FFprobe's display `rotation` in degrees, decoded frame count, `avg_fps` when available, the first source timestamp (`start_time_s`), requested stride, and number of retained frames. For a 90° or 270° rotation the displayed width and height are swapped. Timestamps remain on the source video timeline; `start_time_s` records that timeline's origin, so a viewer that displays time from zero should subtract it before looking up a frame.

Rotated videos are ingested with their orientation metadata and a warning is printed. The current calibration is landscape-only: confirm the displayed orientation and use a calibration made for that orientation before running DPVO. A rotation warning must be resolved before trajectory estimation.

`frames.csv` has these columns:

```csv
frame_index,source_timestamp_s
```

Frame indices refer to the decoded source video, not the renumbered rows in the CSV. For example, a stride of 2 retains frame indices 0, 2, 4, and so on. The timestamps are the original presentation timestamps and preserve variable-frame-rate gaps.

Keep the input video out of Git. The hash and frame table are small metadata artifacts and can be retained with the run outputs.
