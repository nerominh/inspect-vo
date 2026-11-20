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

The command requires `ffprobe` (provided by FFmpeg) on `PATH`. It reads per-frame presentation timestamps and does not synthesize them by dividing the frame index by the nominal FPS. Frames with missing, non-finite, or out-of-order timestamps are rejected with an error.

## Outputs

`video.json` records the resolved source path, SHA-256, frame dimensions, decoded frame count, nominal FPS when available, requested stride, and number of retained frames.

`frames.csv` has these columns:

```csv
frame_index,source_timestamp_s
```

Frame indices refer to the decoded source video, not the renumbered rows in the CSV. For example, a stride of 2 retains frame indices 0, 2, 4, and so on.

Keep the input video out of Git. The hash and frame table are small metadata artifacts and can be retained with the run outputs.
