# Camera calibration files

One file per phone (and camera mode), produced by `inspect-vo calibrate` (build plan step 1).

- Name: `<owner>_<phone-model>_<resolution>_<fps>.txt`, e.g. `minh_pixel7_1080p_30.txt`
- Format (DPVO): one line, `fx fy cx cy k1 k2 p1 p2 k3`, in pixels for full-resolution frames
- Record next to it, in this README: date, square size, number of frames used, RMS reprojection error

| File | Phone | Mode | Date | RMS error (px) |
|---|---|---|---|---|
| | | | | |
