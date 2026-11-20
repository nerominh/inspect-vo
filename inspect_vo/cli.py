"""Command-line entry point: `inspect-vo <command> ...` (build plan step 7).

Each sub-command maps to one pipeline step. Steps that are not built yet
exit with a message saying which step and module to implement.
"""

import argparse
import sys
from pathlib import Path

from inspect_vo import __version__


def _not_built(step: int, module: str):
    def handler(args: argparse.Namespace) -> int:
        print(f"Not implemented yet: build plan step {step} ({module}). See README 'Build plan'.",
              file=sys.stderr)
        return 2
    return handler


def _board(args: argparse.Namespace) -> int:
    from inspect_vo.calibrate import make_board
    print(f"Wrote {make_board(Path(args.out), *args.pattern, args.square_mm)}: print at 100% / actual size")
    return 0


def _calibrate(args: argparse.Namespace) -> int:
    from inspect_vo.calibrate import run
    res = run(Path(args.video), Path(args.out), args.square_mm, tuple(args.pattern), every=args.every,
              max_views=args.max_views, notes=args.notes, free_k3=args.free_k3)
    return 0 if res.quality != "poor" else 1


def _ingest(args: argparse.Namespace) -> int:
    from inspect_vo.ingest import ingest
    try:
        ingest(Path(args.video), Path(args.out), stride=args.stride)
    except (OSError, RuntimeError, ValueError) as exc:
        print(f"Ingest failed: {exc}", file=sys.stderr)
        return 1
    print(f"Ingested {args.video} into {args.out} (stride {args.stride})")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="inspect-vo",
        description="Phone walkthrough video -> metric top-down map of the camera path (DPVO-based).",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    sub = parser.add_subparsers(dest="command", metavar="<command>")

    p = sub.add_parser("board", help="step 1 helper: write a printable checkerboard (A4, 9x6 inner corners)")
    p.add_argument("--out", default="board.png")
    p.add_argument("--pattern", type=int, nargs=2, default=[9, 6], metavar=("COLS", "ROWS"))
    p.add_argument("--square-mm", type=float, default=25.0)
    p.set_defaults(func=_board)

    p = sub.add_parser("calibrate", help="step 1: checkerboard video -> camera calibration file")
    p.add_argument("video", help="checkerboard video recorded in the walkthrough camera mode")
    p.add_argument("--square-mm", type=float, required=True, help="checkerboard square side in mm (measured)")
    p.add_argument("--pattern", type=int, nargs=2, default=[9, 6], metavar=("COLS", "ROWS"),
                   help="inner corners (default: 9 6)")
    p.add_argument("--out", required=True,
                   help="output calib file, e.g. calib/minh_pixel7_1080p_30.txt (.json and _check.jpg go next to it)")
    p.add_argument("--every", type=int, default=5, help="check every Nth frame (default 5)")
    p.add_argument("--max-views", type=int, default=40, help="most views used in the fit (default 40)")
    p.add_argument("--notes", default="", help="phone model, camera app, settings (stored in the .json)")
    p.add_argument("--free-k3", action="store_true", help="also fit k3 (only for wide-angle lenses)")
    p.set_defaults(func=_calibrate)

    p = sub.add_parser("ingest", help="step 2: hash video and map frames to source timestamps")
    p.add_argument("video", help="source video to register")
    p.add_argument("--out", required=True, help="output directory for video.json and frames.csv")
    p.add_argument("--stride", type=int, default=1, help="record every Nth frame (default 1)")
    p.set_defaults(func=_ingest)

    p = sub.add_parser("track", help="step 3: run DPVO on an ingested video")
    p.add_argument("workdir", help="directory written by `ingest`")
    p.add_argument("--calib", required=True)
    p.add_argument("--runs", type=int, default=5, help="repeated DPVO runs (default 5)")
    p.add_argument("--config", default="configs/default.yaml")
    p.set_defaults(func=_not_built(3, "inspect_vo/trajectory.py"))

    p = sub.add_parser("scale", help="step 5: scale the path to metres from one known distance")
    p.add_argument("workdir")
    p.add_argument("--frames", type=int, nargs=2, required=True, metavar=("A", "B"),
                   help="frame indices at the two ends of the known distance")
    p.add_argument("--distance-m", type=float, required=True)
    p.set_defaults(func=_not_built(5, "inspect_vo/scale.py"))

    p = sub.add_parser("flatten", help="step 6: project the path to a top-down 2D map")
    p.add_argument("workdir")
    p.set_defaults(func=_not_built(6, "inspect_vo/flatten.py"))

    p = sub.add_parser("run", help="step 7: run steps 2-6 on one or more videos")
    p.add_argument("videos", nargs="+")
    p.add_argument("--calib", required=True)
    p.add_argument("--out", default="outputs")
    p.set_defaults(func=_not_built(7, "inspect_vo/cli.py + inspect_vo/manifest.py"))

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command is None:
        parser.print_help()
        return 0
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
