# Learned Monocular Visual Odometry for GPS-Denied Building Interiors

COMP3090 Course Related Project II
Team: Nguyen The An, Hoang Anh Tu, Nguyen Quang Huy, Nguyen Duy Minh
Supervisor: Prof. Leandro S. Marcolino

This file summarises the project proposal (`Crp2_Project_Description.pdf`) as a working plan: what we are building, the research questions, the experiments that answer them, and what we expect to see. Setup and run instructions will be added at the end.

---

## 1. The project in one paragraph

Building inspectors film walkthrough videos of interiors, but indoors there is no GPS, so a defect's location is written down by hand ("crack outside room 304"). That breaks down in basements, garages, tunnels and long, uniform corridors, and it makes defects hard to find again on the next visit. We will build an **offline pipeline** that takes an ordinary phone walkthrough video, recovers the camera's path with the learned visual odometry model **DPVO**, scales it to metres using one known distance, and draws it as a **top-down map**. In a minimal viewer, the user scrubs the video and **tags defects**, and a report exports each tag's position, thumbnail and note. The contribution is **an evaluated pipeline and an honest accuracy estimate on inspection-style video**, not a new VO model.

### What a tag means

Tagging works like this:

1. The user scrubs the video and stops on a frame where they see a crack.
2. They click "tag" and maybe type a note, like "crack, ~2 mm, left wall".
3. The system saves the frame number, looks up where the camera was at that frame, and puts a pin on the top-down map there.
4. The report lists each tag with its map position, a thumbnail (the whole frame) and the note.

A tag is not a bounding box on the image. It stores **the camera's position at the tagged frame**, not the 3D position of the crack on the wall. Locating the crack itself is a stretch goal. A "crack" here means a visible linear crack about **1 mm or wider**, filmed from **0.5–2 m**. At 1080p with a ~70° field of view, one pixel covers about 1.5 mm of wall at 2 m, so hairline cracks are out of scope.

### Scope

| In scope (core) | Stretch goals | Out of scope |
|---|---|---|
| Offline processing of monocular RGB video from calibrated phones | 3D position of the crack on the wall | Automatic crack detection |
| One VO backend: DPVO | Loop closure (DPV-SLAM) | Aligning separate visits |
| Metric scale from one user-supplied known distance | | Floor-plan overlay |
| Single-floor top-down map | | On-device processing |
| Manual tagging and report export in a minimal viewer | | Phone AR frameworks (ARCore, ARKit) |

We deliberately avoid ARCore and ARKit. They give metric poses, but only if a dedicated app records the video. Our target is ordinary footage processed after the fact.

### What DPVO is

DPVO (Deep Patch Visual Odometry) is a **trained neural network for computer vision**, not a chatbot and not a server. It does one job:

- **Input:** a video (or a folder of frames) plus the camera calibration.
- **Output:** a file giving where the camera was and which way it pointed at every frame, plus a sparse set of 3D points of the scene.

It runs like a normal program: you start it from the terminal, it processes the video, writes the result file and stops. Nothing keeps running in the background. It needs an NVIDIA GPU to run at a useful speed.

The output has **no real-world scale**: the path has the right shape, but its units are arbitrary. Our pipeline converts it to metres using one known distance.

**We do not train or retrain the network.** We use the pretrained model file published by the DPVO authors (`dpvo.pth`, trained on the synthetic TartanAir dataset) exactly as it is. Our work is the pipeline around it (calibration, scaling, map, viewer) and measuring how accurate it is on real indoor video. Retraining would need large datasets and many GPU-days, and it is not part of the project.

| Machine | Role |
|---|---|
| Our laptop (WSL Ubuntu) | Development: test DPVO, write and debug the pipeline, try short videos |
| Supervisor's server (Linux, large GPUs) | Real runs: the full TUM benchmark and all our recordings, using the same commands |
| Google Colab | Backup if server access is delayed |
| Any computer with a browser | The viewer, which only shows precomputed results and needs no GPU |

---

## 2. Pipeline

```
 phone video ──► 1. Calibrate & ingest ──► 2. Estimate trajectory ──► 3. Scale & flatten ──► 4. Tag & report
                  checkerboard intrinsics   DPVO poses (unknown scale)  known distance → metres   viewer: scrub, tag
                  content hash              sparse point cloud          plane fit → top-down map  JSON / report export
                  timestamp → frame map     flag & split on failures
```

1. **Calibrate and ingest.** Calibrate each phone once with a checkerboard (OpenCV) to get intrinsics and distortion. Register each video by its content hash. Sample frames by source timestamp and keep the mapping back to the original video.
2. **Estimate the trajectory.** Run DPVO (about 96 patches per frame, sliding-window bundle adjustment) to get per-frame 6-DoF poses up to an unknown scale, plus a sparse point cloud. Flag likely tracking failures, such as abrupt pose jumps, and **split the path** rather than output a silently wrong map.
3. **Scale and flatten.** Multiply positions by `known distance / estimated distance`. Fit a plane to the trajectory, take its least-variance axis as vertical (valid for single-floor walks), and project onto that plane to get the top-down map.
4. **Tag and report.** A tag is stored by frame index and mapped to that frame's pose. The report exports position, thumbnail and note for each tag. The viewer reads only precomputed results and needs no GPU.

### Build plan: the pipeline step by step

**Current priority (decided 2026-11-14):** build the pipeline first. The research questions (E2–E4) come after; E1 is already done (section 10.2).

The pipeline is being built step by step, and **DPVO is only one step inside it (step 3)**. The code lives in **our own repository** (`inspect-vo`), separate from `~/DPVO`. DPVO stays an installed dependency that we never edit, so the recorded DPVO commit stays meaningful.

**Status update (2026-11-21):** step 1 calibration (implementation, CLI, guide, and synthetic tests) has been merged into `main` through PR #1. Real phone-video validation is still required. Step 2 ingest and its CLI, VFR timestamp test, orientation-aware metadata, source start time, average FPS field, and guide are implemented on `feat/video-ingest`. The repository suite passes locally; its FFmpeg-generated VFR test skips because the local FFmpeg executable cannot load `libopenh264.so.5`. Pilot-video validation is still pending.

#### First: recordings needed before coding (physical tasks)

The end-to-end pipeline needs real footage for validation; unit-level checks can also use synthetic inputs.

1. **Calibration video.** Print an OpenCV checkerboard (9×6 inner corners), tape it to something flat and rigid, and **measure one square's side** with a ruler (e.g. 25 mm). Record 30–60 s of video of the board:
   - Use the **same camera mode as the walkthroughs**: 1080p, 30 fps, main 1× lens, stabilisation off if the phone allows it, no zoom.
   - Move the board slowly: near and far, tilted, and reaching the corners of the frame.
   - Use video, not photos: phones crop the sensor differently in video mode, so photo calibration gives the wrong numbers.
2. **Pilot walkthrough.** Walk 15–20 m along a corridor (about 1 min), phone steady and roughly level, in the same camera mode. Before filming, put **two tape marks on the floor a measured distance apart** (e.g. 10.00 m) and film yourself passing over both. This is the test case for scaling (step 5).
3. Copy both videos to `~/data/pilot/` in Ubuntu (`\\wsl$\Ubuntu\home\<user>\data\pilot` from Windows).

#### The steps, in the order data flows through them

| # | Step | What we write | Uses | Done when | Current status |
|---|---|---|---|---|---|
| 0 | **Repository skeleton** | Folders per step, a CLI entry point, pytest set-up, README, git | Python | `pytest` runs and the CLI prints its help text | Done on `main` |
| 1 | **Calibrate** (once per phone) | Script: checkerboard video → camera settings and lens distortion, saved in DPVO's calib format `fx fy cx cy k1 k2 p1 p2 k3` | OpenCV | The calib file exists and the reprojection error is under ~0.5 px | Implementation, CLI, guide, and synthetic tests merged into `main`; real phone video and calibration file pending |
| 2 | **Ingest** | Hash the video (its ID); read every frame's **real timestamp**; save a table frame number → video time, so a tag can point back to the exact moment in the original video | FFmpeg | Table and hash exist for the pilot video | Implementation, CLI, VFR timestamp test, rotation-aware metadata, and ingest guide added on `feat/video-ingest`; 15 tests pass and 4 skip locally (the VFR test needs a working FFmpeg runtime); pilot-video validation pending |
| 3 | **Run DPVO** | Feed our frames and calibration to DPVO's Python API; save poses (TUM format) and 3D points; 5 runs | **DPVO, the only step that uses it** | A trajectory file exists for the pilot video (do a quick look with `demo.py` first) | Pending |
| 4 | **Detect failures** | Scan the path for sudden jumps (impossible speed or rotation) and split it into trustworthy segments rather than draw one wrong map | numpy | A deliberately shaken test video gets split | Pending |
| 5 | **Scale to metres** | User gives two frames and the real distance between them → multiply the path by real ÷ estimated distance | numpy | The two pilot floor marks come out ~10 m apart | Pending |
| 6 | **Flatten to a top-down map** | Fit a plane to the path, take its least-varying direction as "up", project onto the floor; save JSON and PNG | numpy, matplotlib | The PNG of the pilot walk looks like the corridor | Pending |
| 7 | **Batch command + manifest** | One command running steps 2–6 on many videos; a manifest per run (video hash, calib, DPVO commit, config, seed); one failed video does not stop the batch | Python CLI | A batch of 2+ videos produces outputs and manifests | Pending |
| 8 | **Tests** | Scaling and flattening on fake paths with known answers; calibration parsing; timestamp → frame mapping | pytest | All tests pass | Calibration-specific synthetic tests merged into `main`; VFR timestamp-to-frame test added on `feat/video-ingest`; scale/flatten tests remain pending |
| 9 | **Viewer** (weeks 5–6) | Web page loading the video and map JSON: scrubbing moves a dot on the map; "tag" saves frame, position and note; "export" writes the report | HTML/JS, no GPU | Tag the pilot's two floor marks and export a report | Pending |
| 10 | **Evaluation scripts** (later, for E3/E4) | Tag error vs. tape-measured marks; loop error; drift vs. distance | Python | Run on the full recording campaign | Pending; E1 passed, follow-up analysis/server run noted in Results log |

**Order:** steps 0–2 first, plus a quick `demo.py` run on the pilot video to see how DPVO handles real footage. Then step 3 with our own ingest, followed by steps 5–6 (small, a few dozen lines each) with their tests. Then steps 4, 7 and 8, then the viewer.

#### Why DPVO's `demo.py` is not enough

`demo.py` already runs DPVO on a video and is useful for a first look. But its video reader (`dpvo/stream.py`, `video_stream`) does not meet the proposal's requirements:

- **No real timestamps.** It numbers frames 0, 1, 2… instead of using the video's real timestamps. Phones often record at a variable frame rate, so these numbers drift from video time and tags would point to the wrong moment.
- **Lost frame mapping.** It halves the resolution and by default keeps only every 2nd frame (`--stride 2`), without recording which original frames were used.
- **Missing steps.** It does no scaling, flattening, failure detection or manifests.

So our step 2 replaces its video reader, and step 3 calls DPVO's Python code directly, the same way `demo.py` and `evaluate_tum.py` do.

### Reproducibility rules

- Each run writes a **manifest**: video hash, calibration file, DPVO code revision and checkpoint, configuration, and random seed. A changed configuration produces a separate output version.
- DPVO picks patches at random, so runs are not deterministic. **Every reported number is the median and spread of 5 runs**, as in the DPVO paper.
- Unit tests cover scale computation and plane projection on synthetic trajectories with known answers, calibration parsing, and timestamp-to-frame mapping.
- A failed video does not stop the rest of the batch.
- The environment is pinned (conda) and documented, so the TUM results can be reproduced on a clean machine.

### Compute

- **Development:** a team laptop running DPVO under WSL Ubuntu. On this machine (RTX 4070 Laptop, 8 GB) the default configuration (about 4.9 GB) should fit. The proposal lists an RTX 4050 (6 GB), which would need DPVO's faster setting.
- **Real runs:** the supervisor's Linux server (48–96 GB GPU memory).
- **Fallback:** Google Colab for the benchmark runs if server access is delayed.

---

## 3. Research questions

| | Question | Data | What answers it |
|---|---|---|---|
| **Q1** | Does DPVO reproduce its published accuracy on TUM RGB-D in our setup, and how much does it degrade on low-texture sequences? | TUM RGB-D (motion-capture ground truth) | ATE RMSE vs. the published 0.089 m; failure rate and ATE on freiburg3 low-texture sequences |
| **Q2** | How large is the position error on our own inspection-style walkthroughs, and how fast does it grow with distance walked? | Our recordings at two sites | Loop error, error at floor marks vs. distance walked, tracking failure rate |
| **Q3** | After scaling from one known distance, how close is a tagged position to its tape-measured position, and does a simple capture protocol reduce that error? | Our recordings, with and without the protocol | **Tag position error** (headline metric), scale consistency |

Q1 checks that our setup works before we trust anything else. Q2 measures how the system behaves on the footage it is built for. Q3 measures the error a user would actually see and tests one cheap way to reduce it.

---

## 4. Data

### TUM RGB-D (Q1)

- **The nine `freiburg1` sequences:** `360`, `desk`, `desk2`, `floor`, `plant`, `room`, `rpy`, `teddy`, `xyz`. They have motion-capture ground truth. This is the set DPVO reports 0.089 m average ATE on, and the repo's `evaluate_tum.py` already runs it.
- **The `freiburg3` structure/texture sequences:** combinations of structure / no structure, texture / no texture, and near / far. They are the low-texture stress test.

### Our own recordings (Q2, Q3)

- **Two sites:** VinUni (Hanoi) and École Polytechnique (France).
- **Three routes per site:**
  1. a 20–50 m corridor;
  2. a closed loop (start and end at the same mark);
  3. one low-landmark space (basement, garage or stairwell).
- **Ground truth:** 5–10 tape-measured floor marks per route, plus at least two known distances (one for scaling, one held out to check scale).
- **Recordings:** each route recorded 2–3 times, **with and without the capture protocol**. In total about 12–20 videos of 1–3 minutes.
- **Calibration:** each phone calibrated once with a checkerboard. The calibration files are shipped with the data.
- **Optional:** the Hilti SLAM Challenge datasets.

---

## 5. Planned experiments

### E1: Reproduce DPVO on TUM `freiburg1` (Q1)

- **Procedure:** run `evaluate_tum.py` with the default config and the published `dpvo.pth` checkpoint, `--trials 5`, on all nine `freiburg1` sequences. The default config is pure VO (no loop closure), which matches the published DPVO number. Repeat on the supervisor's server, and with the faster config on the laptop if needed.
- **Metric:** ATE RMSE after Sim(3) alignment (evo), reported per sequence as the median and spread of 5 runs, plus the average over the nine sequences. Also report FPS and peak GPU memory.
- **Success criterion:** the `freiburg1` average is within 20% of 0.089 m, i.e. **0.071–0.107 m**.

#### E1 in simple terms

**The question:** "Did we install DPVO correctly?"

- **What ATE is.** ATE is the average distance between where DPVO thinks the camera was and where it really was. **Smaller is better.** 0.01 m means DPVO was about 1 cm off; 0.43 m means about 43 cm off.
- **The test.** The DPVO authors tested their program on a public set of 9 short videos (TUM `freiburg1`). For these videos the true camera path is known exactly, because it was measured with a motion-capture system. The authors report an average error of **0.089 m (about 9 cm)**. E1 runs the same program on the same 9 videos on our machine and checks that we get about the same number. Within 20% counts as a pass: anywhere from **0.071 to 0.107 m**.
- **If it matches:** our setup is correct. Later, when DPVO makes big errors on our own building videos, we know the cause is the videos (long corridors, plain walls), not a broken installation.
- **If it doesn't match:** something is wrong with the setup, and we fix it before recording anything.

**Why 5 runs.** DPVO picks the image points it tracks at random, so every run gives slightly different numbers. For each video, the script takes the **middle value (median)** of the 5 runs, which isn't fooled by one lucky or unlucky run. The DPVO paper reports results the same way, so the comparison is fair. A single run (the smoke test) only shows that everything works; it is not the E1 result.

**How to run it:** see section 9.5. Results are recorded in section 10.

### E2: Low-texture stress test on TUM `freiburg3` (Q1)

- **Procedure:** the same as E1, on the `freiburg3` structure/texture sequences. This needs a small script or adapter, because `evaluate_tum.py` lists only `freiburg1`.
- **Metrics:** ATE RMSE (median and spread of 5), and the tracking failure rate (runs or segments flagged by our jump detector, or ATE above a threshold we set before looking at the results).
- **Comparison:** textured vs. untextured sequences at the same structure and distance, so the effect of texture is isolated.

### E3: Drift on our own walkthroughs (Q2)

- **Procedure:** run the full pipeline (calibrate, DPVO, scale, flatten) on every recording, 5 runs each.
- **Metrics:**
  - **Loop error** on the closed-loop routes: the start–end gap divided by the path length (%).
  - **Error vs. distance walked:** at each floor mark, the position error plotted against the path length walked up to that mark. Report the slope, i.e. metres of error per metre walked.
  - **Tracking failure rate:** the fraction of videos or path length split or flagged.
- **Breakdown:** by route type (corridor, loop, low-landmark) and by site.

### E4: Tag position error and the capture protocol (Q3)

- **Procedure:** in the viewer, tag the frame where the camera is over each floor mark. Scale the map using one known distance and compare each tag to the mark's tape-measured position.
- **Metrics:**
  - **Tag position error:** the distance in metres between the tag's map position and the tape-measured position (headline metric). Report the median, the spread, and the 90th percentile.
  - **Scale consistency:** the ratio of the estimated to the true length for the held-out second known distance.
- **Comparison:** recordings with the protocol vs. without, paired by route and site.
- **Success criterion:** provisional target of **≤ 1 m tag error on walks under 50 m**. The target is fixed after the pilot recordings.

### Capture protocol (to be drafted in weeks 1–2)

These are candidate rules, not decided yet:
- walk at a slow, steady pace;
- avoid pure in-place rotation and fast pans;
- keep textured surfaces (door frames, signs, edges) in view in low-landmark areas;
- film the known scale distance at the start;
- start and end on a marked point;
- hold the phone steady and roughly level.

The protocol must stay short (one page) and usable by an inspector without training.

---

## 6. Expected results

These are hypotheses to test, not results. Each one says which outcome would answer its question and how.

| Exp. | Expected result | How it answers the question | If it turns out otherwise |
|---|---|---|---|
| E1 | `freiburg1` average ATE close to 0.089 m (within the 0.071–0.107 m band), with run-to-run spread because patch selection is random. | Q1 (first half): our setup is trustworthy, so later errors come from the footage, not our installation. | Debug the setup (checkpoint, config, calibration, stride) before running anything on our own footage. Report any remaining gap. |
| E2 | Clearly higher ATE and more tracking failures on the no-texture `freiburg3` sequences than on the textured ones. Structure alone helps less than texture, since DPVO tracks image patches. | Q1 (second half): quantifies how much low texture hurts, which predicts trouble in plain corridors and basements. | If degradation is small, low-texture spaces are less of a risk than expected. That is still a reportable finding. |
| E3 | Corridors and loops track, but error grows with distance walked (VO has no loop closure, so drift accumulates). Low-landmark routes show the most failures and the largest drift. Loop error is a few percent of path length. | Q2: gives the actual error level and its growth rate on inspection-style video. | If DPVO tracks our footage poorly, the failures are reported as a Q2 finding, not hidden. |
| E4 | After one-distance scaling, tag error is below about 1 m on short walks and grows on longer ones. The held-out distance shows some scale drift. The protocol lowers both median error and failure rate. | Q3: tells a user how much to trust a tag, and whether a cheap capture rule is worth asking for. | If the protocol shows no benefit, report that. With only 12–20 videos, all results on our own footage are **descriptive**, not statistically conclusive. |

### Why tag position error is the headline metric

ATE is reported for comparability with the DPVO paper, but it flatters the system: its Sim(3) alignment uses the ground truth to fix scale, rotation and position. Tag position error uses only what a real user would have (one known distance), so it reflects the error they would see.

---

## 7. Open decisions to settle with the team or supervisor

- **Map-to-tape frame alignment for E4.** Scaling fixes the scale, but the map also has to be rotated and shifted into the tape-measure frame before tags can be compared. Options:
  - anchor it on the first mark and the direction to the second mark (closest to what a user would do);
  - use a best-fit 2D alignment with the evaluated mark left out.
  The choice changes the numbers, so fix it before evaluating.
- **What counts as a "tracking failure".** Set the jump threshold and ATE cut-off before looking at the results.
- **Which known distance is used for scaling and which is held out,** e.g. always the first marked segment.
- **The final tag-error target,** after the pilot videos.

---

## 8. Timeline (indicative, 8 weeks)

| Weeks | Milestone |
|---|---|
| 1–2 | DPVO environment on the server; phones calibrated; TUM `freiburg1` and `freiburg3` results reproduced (E1, E2); capture protocol drafted; one pilot video per site |
| 3–4 | Own-video pipeline (ingest, trajectory, scaling, map) with manifests and tests; full recording campaign at both sites |
| 5–6 | Evaluation on own footage (E3, E4: loop error, tag position error, scale consistency); minimal viewer with tagging and export |
| 7–8 | Final runs; stretch goals if time allows; documentation, report and demonstration |

**Deliverables:**
- a documented repository with a pinned environment;
- a tested command-line pipeline;
- a minimal tagging viewer;
- our recordings with calibration files and measured marks;
- a one-page capture protocol;
- a reproducible evaluation script;
- the final report.

---

## 9. Setup and run steps

### 9.1 What is already installed (one-time, done)

On the development laptop, everything below runs in **WSL Ubuntu**, not Windows. The setup so far:

- Miniforge (conda) in `~/miniforge3`.
- The DPVO code, cloned with `git clone --recursive https://github.com/princeton-vl/DPVO.git` into `~/DPVO`. That is `/home/<user>/DPVO` in Ubuntu, or `\\wsl$\Ubuntu\home\<user>\DPVO` from Windows.
- The `dpvo` conda environment, created from DPVO's `environment.yml`: Python 3.10, PyTorch 2.3.1, CUDA 12.1.
- The CUDA 12.1 compiler and gcc 12, installed with apt from NVIDIA's WSL repository. The `dpvo` env sets `CUDA_HOME`, `CC`, `CXX` and `TORCH_CUDA_ARCH_LIST` automatically when activated.
- DPVO itself, built with `pip install --no-build-isolation .` inside `~/DPVO`.
- `evo` pinned to 1.37.1 with `pip install "evo==1.37.1"`. DPVO's `environment.yml` doesn't pin `evo`, and evo 1.38.0 removed the `est_name` argument that `evaluate_tum.py` uses, so the script crashes with `TypeError: ape() got an unexpected keyword argument 'est_name'` after the first sequence.

If you ever need to redo the setup on another machine (such as the server), ask for the full install notes. The two non-obvious fixes were installing `nvcc` and switching to gcc 12, because CUDA 12.1 rejects gcc 13.

### 9.2 Starting a work session (every time)

DPVO is not a server, so there is nothing to "boot up". You only need to open the right environment:

```bash
# 1. Open Ubuntu (Start menu → Ubuntu, or type `wsl` in PowerShell)
# 2. Activate the environment
conda activate dpvo
# 3. Go to the code
cd ~/DPVO
```

Optionally, check that the GPU is visible (this should print `True` and the GPU name):

```bash
python -c "import torch; print(torch.cuda.is_available(), torch.cuda.get_device_name(0))"
```

If you forget `conda activate dpvo`, Python errors with `ModuleNotFoundError` (for example `No module named 'torch'`). Activate the env and run again.

### 9.3 One-time downloads

#### a. Pretrained network weights (required, ~13 MB)

```bash
cd ~/DPVO
wget -O models.zip "https://www.dropbox.com/scl/fo/2g6e134ruh1acmaye5bmy/AK0DY9WLZ25elq-7N7sJcB0/models.zip?rlkey=4j336vcc4h324j4p4ji3ppl0t"
unzip models.zip
ls *.pth          # should list dpvo.pth
```

This uses the same link as DPVO's `download_models_and_data.sh`. We don't run the whole script, because the rest of it is not needed:

- `TartanAir.pickle` is only for training, which we do not do.
- `movies.zip` holds demo videos, which are optional.

#### b. TUM RGB-D `freiburg1` sequences (required for E1, ~5.1 GB download)

The data is kept outside the code folder, in `~/datasets`:

```bash
mkdir -p ~/datasets/TUM_RGBD && cd ~/datasets/TUM_RGBD
for s in 360 desk desk2 floor plant room rpy teddy xyz; do
  wget -c https://cvg.cit.tum.de/rgbd/dataset/freiburg1/rgbd_dataset_freiburg1_$s.tgz
  tar -xzf rgbd_dataset_freiburg1_$s.tgz && rm rgbd_dataset_freiburg1_$s.tgz
done
ls   # should show 9 folders named rgbd_dataset_freiburg1_*
```

- `wget -c` resumes a download that was interrupted, so the loop is safe to re-run.
- Each folder contains `rgb/` (the images DPVO uses), `depth/` (ignored, since we use monocular RGB only), `groundtruth.txt` (motion-capture poses) and some `.txt` index files.
- The extracted data takes roughly as much disk space again as the download.

### 9.4 Long runs: use tmux

#### How long the runs take

| Run | Frames processed | Time on the laptop |
|---|---|---|
| E1 smoke test (1 trial) | 8,694 (the nine `freiburg1` sequences) | ~12 min (one fifth of the full run) |
| E1 full run (5 trials) | 43,470 | **61 min (measured 2026-11-14)**, about 1 min per trial |
| Our own videos (later, 12–20 videos × 5 runs) | far more | hours. Run them on the server. |

If the terminal is closed, or an SSH connection to the server drops, any job running in it is killed. **tmux** prevents this: the job runs inside a tmux session, which keeps going after you close the window or disconnect, and you can reattach to it later. tmux is already installed in our Ubuntu (`tmux -V` → 3.4) and is standard on Linux servers. **Run anything that takes more than a few minutes inside tmux.**

#### The commands you need

| Action | Command |
|---|---|
| Start a new named session | `tmux new -s e1` |
| Detach (leave it running, return to the normal terminal) | press `Ctrl+b`, release, then press `d` |
| List sessions | `tmux ls` |
| Reattach to a session | `tmux attach -t e1` |
| Open a second window inside the session | `Ctrl+b` then `c` |
| Switch between windows | `Ctrl+b` then `0` / `1` |
| Scroll up through the output | `Ctrl+b` then `[`, use the arrow keys or PgUp, press `q` to exit |
| End the session (after the job is done) | type `exit` in each window, or run `tmux kill-session -t e1` |

A new tmux session starts in the `base` conda env, so **run `conda activate dpvo` inside the session** before anything else.

#### WSL caveats (laptop only)

- **Keep one Ubuntu window open (minimised is fine) while a job runs.** tmux survives closing the window you started it in, but WSL may shut Ubuntu down completely if no Ubuntu window is open for a while, and that kills tmux too.
- **Don't let the laptop sleep:** plug it in and disable sleep for the duration.
- **Never run `wsl --shutdown` during a run.**

On the server, tmux alone is enough: detach, log out, and reattach later.

### 9.5 Experiment E1: reproduce DPVO on TUM `freiburg1`

`evaluate_tum.py` (in the DPVO repo) does everything for E1:

1. It runs DPVO on all nine `freiburg1` sequences.
2. It aligns each estimated trajectory to the ground truth with Sim(3), using evo.
3. It computes the ATE RMSE.
4. Over `--trials N` runs, it prints each sequence's results and their median, then the average of the nine medians (`AVG`).

The camera calibration for `freiburg1` is built into the script. With the default config, loop closure is off, so this is pure DPVO, the same setting as the published 0.089 m.

Both steps below run inside one tmux session called `e1`.

#### Step 1: smoke test (1 trial)

```bash
tmux new -s e1                 # opens the session (window 0)
conda activate dpvo
cd ~/DPVO
mkdir -p ~/results/E1
python evaluate_tum.py --tumdir ~/datasets/TUM_RGBD --trials 1 2>&1 | tee ~/results/E1/smoke_laptop.log
```

You can watch it run, or detach with `Ctrl+b` then `d` and come back later with `tmux attach -t e1`. The output is also saved to the `.log` file, so nothing is lost while detached.

This checks that the data, the weights and the GPU all work before the long run. It should end with a line `AVG:  0.0xx`. One trial is already a rough check: the number should land somewhere near 0.089.

#### Step 2: the real E1 run (5 trials, as in the proposal)

Run this in the same tmux session (reattach with `tmux attach -t e1` if you detached). If you are starting fresh, first run `tmux new -s e1`, then `conda activate dpvo`.

**Check the prompt starts with `(dpvo)`, not `(base)`.** A new tmux shell always starts in `base`, which has no DPVO, OpenCV etc. Running there fails with `ModuleNotFoundError: No module named 'cv2'`, and `conda env export` would record the wrong environment. The first line below prints `env OK` or a warning. If it warns, don't run the rest:

```bash
[ "$CONDA_DEFAULT_ENV" = dpvo ] && echo "env OK" || echo "WRONG ENV: run 'conda activate dpvo' first"
cd ~/DPVO
git rev-parse HEAD                 > ~/results/E1/dpvo_commit.txt
conda env export                   > ~/results/E1/environment.lock.yml
nvidia-smi                         > ~/results/E1/gpu.txt
cp config/default.yaml               ~/results/E1/

time python evaluate_tum.py --tumdir ~/datasets/TUM_RGBD --trials 5 --plot --save_trajectory \
     2>&1 | tee ~/results/E1/e1_default_laptop.log
```

- The first four commands write a simple manifest: the code version, the exact environment, the GPU and the config.
- `--plot` saves a trajectory plot per sequence and trial in `~/DPVO/trajectory_plots/` (PDF).
- `--save_trajectory` saves each estimated trajectory in TUM format in `~/DPVO/saved_trajectories/`.
- `time` prints the total run time at the end. Divide the total number of frames processed by the time for a rough FPS figure (it includes image loading).
- The script also leaves `poses_*.npy` and `tstamps_*.npy` files in `~/DPVO`. These are intermediate files and can be ignored.

After the run, move the outputs next to the log:

```bash
mv ~/DPVO/trajectory_plots ~/DPVO/saved_trajectories ~/results/E1/
```

**Peak GPU memory:** right after starting the run, open a second window in the same tmux session (`Ctrl+b` then `c`) and run:

```bash
nvidia-smi --query-gpu=memory.used --format=csv -l 1 | tee ~/results/E1/gpu_memory.log
```

Switch back to the run with `Ctrl+b` then `0`. When the run finishes, go to window 1 (`Ctrl+b` then `1`) and stop the monitor with `Ctrl+C`. The largest value in `gpu_memory.log` is the peak. You can then close the session with `tmux kill-session -t e1`.

**Checking on the run later:** `tmux attach -t e1` shows the live output. Without attaching, `tail -n 20 ~/results/E1/e1_default_laptop.log` shows the latest lines. The run is finished when the log ends with `AVG:` and the time summary (`real ...`).

#### Step 3: read the result

The log ends with one line per sequence (the median of 5 trials), then `AVG:`. For example (illustrative numbers only):

```
rgbd_dataset_freiburg1_360 [0.11, 0.12, 0.13, 0.15, 0.16]   ← all 5 trials, sorted
...
rgbd_dataset_freiburg1_360 0.13                            ← median of the 5
...
AVG:  0.09
```

| `AVG` | Meaning |
|---|---|
| 0.071–0.107 m | E1 passes: within 20% of the published 0.089 m. The setup is trustworthy. |
| Above 0.107 m | Check the trial spread per sequence first (one bad sequence can pull the average up), then check the weights file and config. Record the result either way. |

For the report, copy each sequence's median and its min–max over the 5 trials into a table, together with `AVG`, run time and peak GPU memory.

#### If something goes wrong

| Symptom | Fix |
|---|---|
| `ModuleNotFoundError: No module named 'cv2'` (or `torch`) and the prompt shows `(base)` | You are in the wrong conda env, usually because tmux started a fresh shell. Run `conda activate dpvo` and rerun. Also regenerate `environment.lock.yml` if it was written from `base` (its first line says `name: base`). |
| `TypeError: ape() got an unexpected keyword argument 'est_name'` | `evo` is too new. Run `pip install "evo==1.37.1"` (see 9.1). |
| `CUDA out of memory` | Run again with `--config config/fast.yaml` (fewer patches, less memory) and note in the log that the fast setting was used. Close other GPU programs first. |
| `FileNotFoundError ... groundtruth.txt` | A sequence is missing or its folder is misnamed. All nine `rgbd_dataset_freiburg1_*` folders must be in `~/datasets/TUM_RGBD`. |
| `No such file ... dpvo.pth` | Run the command from `~/DPVO`, or pass `--network /full/path/to/dpvo.pth`. |
| Run on the server instead | Same commands. Set `TORCH_CUDA_ARCH_LIST` to the server GPU's value (or leave it unset) when building there. |

#### Notes for E2 (later)


`evaluate_tum.py` only works for `freiburg1`. Its list of sequences and its calibration are written into the script itself. The `freiburg3` sequences use a different camera (intrinsics `535.4 539.2 320.1 247.6`, already undistorted; see `calib/tum3.txt`). E2 therefore needs a copy of the script with the `freiburg3` sequence list and that calibration, without the undistortion step.

---

## 10. Results log

Newest entries go at the bottom. Each entry records the setup, so results from different machines or settings are not mixed up.

### 10.1 E1 smoke test: 1 trial, laptop (2026-11-11)

**Setup**

| Item | Value |
|---|---|
| Machine | Laptop, RTX 4070 Laptop GPU (8 GB), WSL Ubuntu 24.04 |
| DPVO commit | `0ac95b6` |
| Weights | `dpvo.pth` (published, not retrained) |
| Config | `config/default.yaml` (96 patches per frame, no loop closure) |
| Software | PyTorch 2.3.1, CUDA 12.1, evo 1.37.1 |
| Command | `python evaluate_tum.py --tumdir ~/datasets/TUM_RGBD --trials 1` |
| Log | `~/results/E1/smoke_laptop.log` |
| Run time / peak GPU memory | not recorded for this run |

**Results** (ATE RMSE after Sim(3) alignment, metres)

| Sequence | What the camera does | ATE (m) | ≈ cm |
|---|---|---|---|
| `xyz` | slow back-and-forth moves over a desk | 0.011 | 1 |
| `desk` | handheld sweep over an office desk | 0.035 | 3 |
| `rpy` | rotates on the spot (roll, pitch, yaw) | 0.037 | 4 |
| `plant` | circles around a plant | 0.044 | 4 |
| `floor` | sweeps along the floor | 0.055 | 6 |
| `desk2` | desk scene, faster motion | 0.070 | 7 |
| `360` | turns a full circle on the spot, fast rotation | 0.121 | 12 |
| `teddy` | circles around a teddy bear | 0.157 | 16 |
| `room` | walks around a whole office room, the longest path | 0.429 | 43 |
| **Average** | | **0.107** | **11** |

**Verdict:** the setup works end to end. The average of 0.107 m is just inside the E1 pass band (0.071–0.107 m), but this is a single trial and is **not** the E1 result. The 5-trial run (Step 2 in 9.5) decides E1.

**Interpretation**

- **What ATE means.** For every frame, it is the distance between where DPVO says the camera was and where the motion-capture system measured it. RMSE is the "typical" distance over all frames, weighted towards large errors. Before measuring, evo shifts, rotates and scales DPVO's path to fit the ground truth as well as possible (Sim(3) alignment). This step is needed because monocular DPVO has no real-world scale, but it also means ATE is an optimistic number.
- **Most sequences are accurate to a few centimetres.** Six of the nine are between 1 and 7 cm. These are short, slow handheld recordings of textured desk scenes, which suit DPVO well.
- **The error grows with path length.** `room` has the longest path and by far the largest error (43 cm). DPVO is odometry without loop closure: each small error is built on by the next frame, so drift accumulates with distance. This is the same effect Q2 measures on our own walkthroughs, which are longer still (20–50 m corridors).
- **Fast rotation is hard.** `360` (12 cm) is mostly rotation in place, where consecutive frames overlap less and there is little sideways motion to judge depth from.
- **One sequence decides the average.** Without `room`, the average of the other eight would be about 0.066 m. So whether E1 passes depends mainly on how `room` behaves over 5 trials, and the report should show per-sequence numbers, not just the average.
- **Check `teddy`.** At 16 cm it is high compared with the similar `plant` sequence (4 cm). It may be a bad random run (DPVO picks patches randomly). The 5-trial median will show whether it is consistently high.
- **What this means for the project.** E1 is only a check that our installation reproduces DPVO's published accuracy. If it passes, any large errors later on our own videos can be blamed on the footage (long paths, low texture), not on our setup.

**To do:** compare each sequence with the per-sequence TUM table in the DPVO paper, and run the 5-trial E1 with run time and peak GPU memory recorded.

### 10.2 E1 full run: 5 trials, laptop (2026-11-14) ✅ PASS

**Setup:** identical to 10.1 (laptop RTX 4070 8 GB, DPVO `0ac95b6`, published `dpvo.pth`, `config/default.yaml`, evo 1.37.1), except `--trials 5 --plot --save_trajectory`. The manifest is in `~/results/E1/`: `dpvo_commit.txt`, `environment.lock.yml` (env `dpvo`), `gpu.txt`, `default.yaml`, and the log `e1_default_laptop.log`. There are 45 trajectory plots (PDF) and 45 estimated trajectories (TUM format).

**Results** (ATE RMSE after Sim(3) alignment, metres. All 5 trials are sorted from best to worst; the median is the reported value.)

| Sequence | Trials (sorted) | **Median** | Range (worst − best) | Smoke test (1 trial) |
|---|---|---|---|---|
| `xyz` | 0.010 · 0.010 · 0.010 · 0.011 · 0.011 | **0.010** | 0.001 | 0.011 |
| `desk` | 0.018 · 0.021 · 0.023 · 0.023 · 0.026 | **0.023** | 0.008 | 0.035 |
| `rpy` | 0.030 · 0.031 · 0.035 · 0.036 · 0.044 | **0.035** | 0.015 | 0.037 |
| `plant` | 0.035 · 0.037 · 0.038 · 0.040 · 0.057 | **0.038** | 0.022 | 0.044 |
| `floor` | 0.047 · 0.048 · 0.050 · **0.140 · 0.196** | **0.050** | 0.149 | 0.055 |
| `desk2` | 0.043 · 0.053 · 0.064 · 0.071 · 0.080 | **0.064** | 0.036 | 0.070 |
| `360` | 0.102 · 0.118 · 0.118 · 0.133 · 0.147 | **0.118** | 0.045 | 0.121 |
| `teddy` | 0.104 · 0.106 · 0.125 · 0.144 · 0.195 | **0.125** | 0.091 | 0.157 |
| `room` | 0.284 · 0.304 · 0.313 · 0.362 · 0.416 | **0.313** | 0.132 | 0.429 |
| **Average of medians** | | **0.086** | | 0.107 |

| Other measurements | Value |
|---|---|
| Published DPVO average | 0.089 m |
| Our average vs. published | 0.086 m, **3% lower**: inside the 0.071–0.107 m pass band |
| Total run time | 61 min 10 s for 43,470 frames |
| End-to-end speed | **≈ 12 frames/s**. This includes image loading and undistortion on the CPU, model start-up for each trial, evo evaluation and saving plots, so it is **not** DPVO's own speed. The paper's ~60 FPS is DPVO alone. |
| GPU memory | ~1.2 GB in use during spot checks (of 8 GB). Peak not logged: the memory monitor was not running. |

**Verdict: E1 passes.** Our installation reproduces DPVO's published TUM `freiburg1` accuracy (0.086 m vs. 0.089 m). This answers the first half of Q1: yes, DPVO reproduces its published accuracy in our setup.

**Analysis**

1. **Accuracy matches the paper.** The average of the medians is within 3% of the published value. The setup (install, weights, config, evaluation) is correct, so later errors on our own footage can be blamed on the footage, not on the installation.
2. **The smoke test was pessimistic.** Its single trial gave 0.107 m, at the edge of the pass band. With 5 trials the median drops to 0.086 m. Seven of the nine smoke-test values lie inside their 5-trial ranges, mostly near the worse end, and two (`desk` 0.035 and `room` 0.429) were worse than all 5 trials. This shows why a single run is not enough.
3. **Run-to-run variation depends on the sequence.**
   - `xyz` is almost perfectly repeatable (±1 mm).
   - `room` varies by 13 cm between its best and worst trial.
   - `teddy` varies by 9 cm.
   Because of DPVO's random patch selection, the same video can give quite different errors.
4. **Occasional bad runs happen even on easy videos.** On `floor`, three trials are at about 5 cm, but two are 3–4 times worse (14 and 20 cm). This looks like DPVO sometimes losing track briefly; the plots `..._floor_Trial0X.pdf` should show where. The median hides these bad runs, but a real user running the system once could get one.
5. **Long paths give the largest error.** `room`, which walks around a whole office, has the largest error by far (31 cm median) and dominates the average: without it, the average of the other eight is 0.058 m. Error accumulates with distance because DPVO has no loop closure.
6. **Speed is fine for offline use.** At about 12 frames/s end to end, a 3-minute phone video at 30 fps (about 5,400 frames) would take roughly 7–8 minutes per run on the laptop. DPVO's own speed and peak GPU memory still need a proper measurement.

**Implications for the project**

- **Q1 (first half) is answered.** The next step for Q1 is E2: how much worse it gets on low-texture sequences.
- **Expect much larger errors on our walkthroughs (Q2).** The TUM videos are short, handheld and in textured rooms. Even here, the longest path (`room`) gives about 30 cm error, and that is with ground-truth Sim(3) alignment, which flatters the result. Our corridors (20–50 m) are longer, plainer and walked rather than handheld. Error will grow (Q2 measures how fast), and the proposal's ≤ 1 m tag-error target may be tight on longer walks.
- **Always report the median and the spread over 5 runs**, as the proposal planned. The `floor` and `room` spreads show that a single run can be misleading in either direction.
- **The tracking-failure detector matters.** The bad `floor` trials show that DPVO can go wrong without crashing. For our own videos, the pipeline's "flag abrupt pose jumps and split the path" step is essential, and running a video more than once (taking the median, or flagging disagreement between runs) is a cheap safeguard.

**Still to do for E1**

- Compare each median with the per-sequence TUM table in the DPVO paper.
- Look at the `floor` trials 4–5 and the `room` plots to see where tracking drifts.
- Measure DPVO's own FPS and peak GPU memory.
- Repeat E1 on the supervisor's server.
