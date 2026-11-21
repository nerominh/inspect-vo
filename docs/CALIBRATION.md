# Phone calibration

DPVO needs to know each phone camera's focal length, image centre and lens distortion. We measure
them once per phone by filming a printed checkerboard. Takes about 20 minutes, needs no GPU, and
runs on any laptop (Windows, macOS or Linux).

**One calibration is valid for one phone + one lens + one resolution + one orientation + one app and
its settings.** Change any of them and you must calibrate again. So decide the recording setup
first, then calibrate with exactly that setup, then never change it.

## 1. Fix the recording setup (both sites, before anything else)

| Setting | Value | Why |
| --- | --- | --- |
| Resolution / frame rate | 1080p, 30 fps | Same as the calibration; DPVO doesn't need more |
| Orientation | **Landscape**, always | Portrait swaps width/height and invalidates the calibration |
| Lens / zoom | Main camera, 1x, never zoom | Each lens and zoom level is a different camera |
| Stabilization | **Off** | Stabilization crops and warps every frame differently, so the true camera changes frame to frame |
| HDR / format | HDR off, H.264 | 10-bit HDR HEVC may not decode in OpenCV |
| Focus | Locked (at ~2 m) | Refocusing slightly changes the focal length |

How to get there (menu names vary by phone and OS version; check yours):

- **iPhone.** The built-in Camera app can't fully turn stabilization off. Use the free **Blackmagic
  Camera** app, which lets you set stabilization off, fix the lens, lock focus and set 1080p30. If
  you must use the built-in app: Settings > Camera > Record Video: 1080p at 30 fps, HDR Video off,
  Enhanced Stabilization off, **Lock Camera on** (stops automatic lens switching). Settings > Camera >
  Formats: **Most Compatible** (H.264). Long-press on the screen to lock focus and exposure (AE/AF LOCK).
- **Android.** Use the free **Open Camera** app (works on almost every phone) or Blackmagic Camera if
  your phone is supported. In Open Camera: Settings > Video settings: resolution 1080p, frame rate 30,
  **Video stabilization off**; set focus mode to locked/manual. Stay on the 1x main lens.

Write down phone model, app and settings; they go into `--notes` below.

## 2. Print the board

```bash
# in the dpvo env with inspect-vo installed (see README), or on any laptop:
#   pip install numpy opencv-python pyyaml matplotlib && pip install --no-deps -e .
inspect-vo board --out board.png
```
Print `board.png` on A4 at **100% / actual size** (not "fit to page"), on matte paper. Tape it flat to
cardboard or a clipboard; a bent board ruins calibration. Measure one square with a ruler. It should
be 25 mm; if your printer scaled it, use the measured value. (The square size doesn't affect the
camera values DPVO needs; it is recorded for completeness, so a ruler is accurate enough.)

The PNG includes 300 DPI print metadata and an A4 landscape canvas with a white border.
Choose landscape orientation and disable any automatic scaling. Custom boards must also fit A4;
reduce `--square-mm` or `--pattern` if the command reports that the board is too large.

## 3. Film the board (30-60 seconds)

Use the phone, app and settings from step 1. Put the board on a table or wall in even light without
glare, and move the **phone**, slowly:
- the whole board always visible, never cut off at the frame edge;
- move it through the **centre, all four corners and all four edges** of the frame (distortion is
  strongest at the edges; if the board never goes there, the tool will warn you);
- tilt the phone left/right/up/down by roughly 30-45 degrees;
- vary the distance, about 0.4 to 1.2 m;
- move slowly enough that the board is sharp, pausing briefly at each position.

## 4. Run the calibration

```bash
inspect-vo calibrate ~/data/pilot/checkerboard.mp4 --square-mm 25.0 \
    --out calib/huy_iphone13_1080p_30.txt \
    --notes "iPhone 13, Blackmagic Camera, 1080p30, stabilization off, focus locked"
```
Name the file as `calib/README.md` says (`<owner>_<phone-model>_<resolution>_<fps>.txt`). It writes:
- `huy_iphone13_1080p_30.txt`: the camera line DPVO uses (`fx fy cx cy k1 k2 p1 p2 k3`);
- `huy_iphone13_1080p_30.json`: full record (error, coverage, image size, video checksum, notes);
- `huy_iphone13_1080p_30_check.jpg`: detected corners and an undistorted frame.

`--out` must end in `.txt`. In the JSON record, `notes` stores calibration warnings and
`capture_notes` stores the phone/app/settings text supplied with `--notes`.

The command exits with code 1 if the quality is POOR.

## 5. Check the result

The tool prints `QUALITY: GOOD / USABLE / POOR`:

| | Means | Do |
| --- | --- | --- |
| GOOD | Error under 0.5 px, corners seen across 70%+ of the frame | Use it |
| USABLE | Error under 1 px, but coverage or another check is weak | Usable; re-film if it's quick, following the printed NOTE |
| POOR | High error, or the lens model misbehaves near the frame corners | Don't use; re-film following the NOTE |

Then open `_check.jpg`: in the right half, the board's edges and other straight lines (door frames)
should be straight. Typical phone main cameras come out at roughly 65-80 degrees horizontal field of
view; the tool prints it.

## 6. Hand it over

Commit the `.txt` and `.json` to `calib/` (small text files) and add a row to the table in
`calib/README.md`. Keep the videos and the `_check.jpg` out of git. Every walkthrough video from that
phone uses that calibration, and its file name and hash go into each run's manifest.

## Why k3 is fixed at 0

The lens model has up to three radial terms (k1, k2, k3). For a normal phone lens, k3 adds nothing
but trades off against k2 when the board doesn't reach the frame corners. In our synthetic test, a
fit with k3 free matched the board perfectly yet misplaced pixels near the image corners by about
465 px, while the fit with k3 fixed at 0 was off by under 7 px. Use `--free-k3` only for a
wide-angle (0.5x) lens, and only with full corner coverage.
