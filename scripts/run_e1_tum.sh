#!/usr/bin/env bash
# Experiment E1: reproduce DPVO on TUM RGB-D freiburg1 (5 trials, median per sequence).
# See docs/PROJECT_PLAN.md section 9.5. Result on the laptop (2026-11-14): AVG 0.086 m (published 0.089).
# Run inside tmux, in the dpvo env:   bash scripts/run_e1_tum.sh [tag]
set -euo pipefail

TAG="${1:-laptop}"
DPVO_DIR="${DPVO_DIR:-$HOME/DPVO}"
TUM_DIR="${TUM_DIR:-$HOME/datasets/TUM_RGBD}"
OUT="${OUT:-$HOME/results/E1_$TAG}"

[ "${CONDA_DEFAULT_ENV:-}" = dpvo ] || { echo "Wrong env: run 'conda activate dpvo' first" >&2; exit 1; }

mkdir -p "$OUT"
cd "$DPVO_DIR"
git rev-parse HEAD        > "$OUT/dpvo_commit.txt"
conda env export          > "$OUT/environment.lock.yml"
nvidia-smi                > "$OUT/gpu.txt"
cp config/default.yaml      "$OUT/"

( time python evaluate_tum.py --tumdir "$TUM_DIR" --trials 5 --plot --save_trajectory ) \
  2>&1 | tee "$OUT/e1_default.log"

mv trajectory_plots saved_trajectories "$OUT/"
echo "Done. Results in $OUT"
