# inspect-vo

**Learned monocular visual odometry for GPS-denied building interiors.**

`inspect-vo` turns an ordinary phone walkthrough video of a building interior into a **metric top-down map of the camera path**. On that map, a user tags defects such as cracks and exports a report. The camera path comes from [DPVO](https://github.com/princeton-vl/DPVO) (Deep Patch Visual Odometry), a pretrained neural network used as is.

COMP3090 Course Related Project II
Team: Nguyen The An, Hoang Anh Tu, Nguyen Quang Huy, Nguyen Duy Minh
Supervisor: Prof. Leandro S. Marcolino

The full plan, with experiments, setup notes and results, is in [`docs/PROJECT_PLAN.md`](docs/PROJECT_PLAN.md). The original proposal is [`docs/proposal.pdf`](docs/proposal.pdf).

---

## Why

Building inspectors film walkthroughs, but indoors there is no GPS, so defect locations are noted by hand ("crack outside room 304"). That fails in basements, garages, tunnels and long uniform corridors. This project builds an **offline** tool that recovers where the camera was from the video alone, and **measures honestly how accurate that is** on inspection-style footage.

## What it does

1. Record a walkthrough with a normal phone (no AR app; a free camera app may be needed to turn stabilisation off, see [`docs/CALIBRATION.md`](docs/CALIBRATION.md)).
2. Run the pipeline on a GPU machine. It produces a top-down map of the walk, in metres.
3. In the viewer, scrub the video, tag the frames where a crack is visible, add a note, and export a report.

**A tag stores the camera's position at the tagged frame**, not the crack's position on the wall, and it is not a bounding box. Tagging works like this:

1. The user stops the video on a frame where they see a crack.
2. They click "tag" and maybe type a note.
3. The system saves the frame number, looks up where the camera was at that frame, and pins it on the map.
4. The report lists each tag with its map position, a thumbnail of the frame, and the note.

| In scope | Stretch goals | Out of scope |
|---|---|---|
| Offline processing of phone video; DPVO as the only VO backend; metric scale from one known distance; single-floor top-down map; manual tagging and report export | 3D crack position on the wall; loop closure (DPV-SLAM) | Automatic crack detection; aligning separate visits; floor-plan overlay; on-device or real-time processing; retraining DPVO |

## Pipeline

```
phone video ─► 1 calibrate ─► 2 ingest ─► 3 DPVO ─► 4 detect failures ─► 5 scale ─► 6 flatten ─► map.json / map.png ─► 9 viewer: tag & report
               (once/phone)   hash +       poses,     split the path       one known   plane fit →
                              timestamps   no scale   at tracking jumps    distance    top-down
```

DPVO is used only in step 3. Everything else is our code. DPVO is a separate, unmodified dependency, and its commit is recorded in every run manifest.

## Build plan

We build the pipeline first; the research experiments come after. Each step has a check that says when it is done.

**Before coding, record two videos** with the phone, in the same camera mode as the walkthroughs (1080p, 30 fps, main 1× lens, stabilisation off if possible, no zoom):

1. **A calibration video:** 30–60 s of a printed OpenCV checkerboard (9×6 inner corners) seen near and far, tilted, and reaching the corners of the frame. Measure the square size with a ruler. Use video, not photos: phones crop the sensor differently in video mode.
2. **A pilot walkthrough:** 15–20 m of corridor, about 1 min, passing over **two tape marks on the floor a measured distance apart** (e.g. 10.00 m).

Keep the videos in `~/data/pilot/`, not in git.

| # | Step | Module | What it does | Done when | Status |
|---|---|---|---|---|---|
| 0 | Repository skeleton | the whole repo | Package, CLI, tests, configs | `pytest` passes and `inspect-vo --help` works | ✅ |
| 1 | Calibrate | `inspect_vo/calibrate.py` | Checkerboard video → intrinsics and distortion, saved in DPVO's format `fx fy cx cy k1 k2 p1 p2 k3` | Calib file exists and the reprojection error is under ~0.5 px | 🟡 code + tests done ([guide](docs/CALIBRATION.md)); needs a real phone video |
| 2 | Ingest | `inspect_vo/ingest.py` | Video content hash; table of frame index → **real source timestamp**, so tags point back to the exact moment | Hash and frame table exist for the pilot video | ⬜ |
| 3 | Run DPVO | `inspect_vo/trajectory.py` | Feed our frames and calibration to DPVO's Python API; save poses (TUM format) and the point cloud; repeated runs | Trajectory file exists for the pilot video (look at it with DPVO's `demo.py` first) | ⬜ |
| 4 | Detect failures | `inspect_vo/failures.py` | Flag sudden pose jumps (impossible speed or rotation) and split the path into trustworthy segments | A deliberately shaken test video gets split | ⬜ |
| 5 | Scale to metres | `inspect_vo/scale.py` | Two frames plus their real distance → scale factor applied to the whole path | The pilot's two floor marks come out at the measured distance (±) | ⬜ |
| 6 | Flatten | `inspect_vo/flatten.py` | Fit a plane to the path, take its least-varying axis as "up", project to 2D; write `map.json` and `map.png` | The pilot's map looks like the corridor | ⬜ |
| 7 | Batch + manifest | `inspect_vo/cli.py`, `inspect_vo/manifest.py` | One command runs steps 2–6 on many videos; writes a manifest per run (video hash, calibration, DPVO commit and weights, config, seed); one failed video does not stop the batch | A batch of 2+ videos produces outputs and manifests | ⬜ |
| 8 | Tests | `tests/` | Scale and flatten on synthetic paths with known answers; calibration parsing; timestamp → frame mapping | All tests pass, none skipped | ⬜ |
| 9 | Viewer | `viewer/` | Static web page: video and map side by side; scrubbing moves a dot on the map; tag, note, export report. No GPU needed | Tag the pilot's floor marks and export a report | ⬜ |
| 10 | Evaluation | `evaluation/` | Tag error vs. tape-measured marks, loop error, drift vs. distance walked | Runs on the full recording campaign | ⬜ |

**Order:** 0 → 1 → 2 (plus a quick look at the pilot video with DPVO's `demo.py`) → 3 → 5 → 6 → 4 → 7 → 8 → 9 → 10.

**Why not just use DPVO's `demo.py`?** Its video reader numbers frames 0, 1, 2… instead of using real timestamps (phones often record at a variable frame rate). It halves the resolution and by default skips every other frame without recording which ones it used. It also does no scaling, flattening, failure detection or manifests. Our step 2 replaces its reader, and step 3 calls DPVO's Python code directly.

## Repository layout

```
inspect-vo/
├── README.md
├── pyproject.toml          # package + `inspect-vo` command
├── inspect_vo/             # the pipeline, one module per step
│   ├── cli.py              #   command-line entry point (step 7)
│   ├── calibrate.py        #   step 1
│   ├── ingest.py           #   step 2
│   ├── trajectory.py       #   step 3 (the only module that imports DPVO)
│   ├── failures.py         #   step 4
│   ├── scale.py            #   step 5
│   ├── flatten.py          #   step 6
│   └── manifest.py         #   step 7
├── tests/                  # pytest (step 8)
├── configs/default.yaml    # pipeline settings
├── calib/                  # one calibration file per phone (small text files, committed)
├── viewer/                 # step 9
├── evaluation/             # step 10
├── scripts/                # experiment runners, e.g. E1 on TUM
└── docs/                   # full project plan, proposal, capture protocol
```

**Not in git:** videos, datasets, DPVO itself, model weights, and run outputs. They are too large; keep them in a shared drive. See `.gitignore`.

## Setup

Everything runs in **Linux** (WSL Ubuntu on Windows laptops, or the supervisor's Linux server) with an NVIDIA GPU.

1. **Install DPVO** in a conda env named `dpvo`, following [`docs/PROJECT_PLAN.md` §9](docs/PROJECT_PLAN.md). The non-obvious fixes:
   - use Linux, not Windows (the pinned PyTorch/scatter combination only exists for Linux);
   - install CUDA 12.1 `nvcc` and gcc 12;
   - build with `pip install --no-build-isolation .`;
   - pin `evo==1.37.1`.
   Pinned versions: DPVO commit `0ac95b6`, PyTorch 2.3.1, CUDA 12.1, Python 3.10.
2. **Install this repo** into the same env:

   ```bash
   conda activate dpvo
   git clone https://github.com/nerominh/inspect-vo.git ~/inspect-vo
   cd ~/inspect-vo
   pip install --no-deps -e .     # --no-deps: the dpvo env already has numpy, opencv, pyyaml, matplotlib
   pytest                         # skeleton check
   inspect-vo --help
   ```

## Usage (planned; commands fill in as steps are built)

```bash
inspect-vo board     --out board.png                                   # printable checkerboard (built)
inspect-vo calibrate ~/data/pilot/checkerboard.mp4 --square-mm 25 --out calib/phone_minh.txt   # (built)
inspect-vo ingest    ~/data/pilot/corridor.mp4 --out outputs/corridor/
inspect-vo track     outputs/corridor/ --calib calib/phone_minh.txt --runs 5
inspect-vo scale     outputs/corridor/ --frames 120 840 --distance-m 10.0
inspect-vo flatten   outputs/corridor/
inspect-vo run       ~/data/pilot/*.mp4 --calib calib/phone_minh.txt   # steps 2–6 in one go
```

## Research questions (after the pipeline)

| | Question | Status |
|---|---|---|
| **Q1** | Does DPVO reproduce its published accuracy on TUM RGB-D, and how much worse is it on low-texture scenes? | **E1 passed:** 0.086 m average ATE on TUM `freiburg1` (published 0.089 m), median of 5 runs. Low-texture test (E2, `freiburg3`) to do. |
| **Q2** | How large is the position error on our own walkthroughs, and how fast does it grow with distance walked? | Planned: E3 |
| **Q3** | After scaling from one known distance, how close is a tag to its tape-measured position, and does a simple capture protocol help? | Planned: E4, headline metric **tag position error** (provisional target ≤ 1 m on walks under 50 m) |

Data: TUM RGB-D (`freiburg1`, `freiburg3`), plus our own recordings at VinUni (Hanoi) and École Polytechnique (France): 3 routes per site, 5–10 tape-measured floor marks per route, recorded with and without the capture protocol. Every number is reported as the median and spread of 5 runs, because DPVO is not deterministic.

## References

1. Z. Teed, L. Lipson, J. Deng. *Deep Patch Visual Odometry.* NeurIPS 2023. [code](https://github.com/princeton-vl/DPVO)
2. X. Liu et al. *CityWalker: Learning Embodied Urban Navigation from Web-Scale Videos.* CVPR 2025.
3. J. Sturm et al. *A Benchmark for the Evaluation of RGB-D SLAM Systems.* IROS 2012.
4. L. Lipson, Z. Teed, J. Deng. *Deep Patch Visual SLAM.* ECCV 2024.
5. M. Grupp. *evo: Python package for the evaluation of odometry and SLAM.* [code](https://github.com/MichaelGrupp/evo)
6. Hilti SLAM Challenge datasets, 2021–2023.
