"""Command-line entry point: `inspect-vo <command> ...` (build plan step 7).

Each sub-command maps to one pipeline step. Steps that are not built yet
exit with a message saying which step and module to implement.
"""

import argparse
import sys

from inspect_vo import __version__


def _not_built(step: int, module: str):
    def handler(args: argparse.Namespace) -> int:
        print(f"Not implemented yet: build plan step {step} ({module}). See README 'Build plan'.",
              file=sys.stderr)
        return 2
    return handler


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="inspect-vo",
        description="Phone walkthrough video -> metric top-down map of the camera path (DPVO-based).",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    sub = parser.add_subparsers(dest="command", metavar="<command>")

    p = sub.add_parser("calibrate", help="step 1: checkerboard video -> camera calibration file")
    p.add_argument("video", help="checkerboard video recorded in the walkthrough camera mode")
    p.add_argument("--square-mm", type=float, required=True, help="checkerboard square side in mm")
    p.add_argument("--pattern", type=int, nargs=2, default=[9, 6], metavar=("COLS", "ROWS"),
                   help="inner corners (default: 9 6)")
    p.add_argument("--out", required=True, help="output calib file, e.g. calib/phone_minh.txt")
    p.set_defaults(func=_not_built(1, "inspect_vo/calibrate.py"))

    p = sub.add_parser("ingest", help="step 2: hash video, extract frames with real timestamps")
    p.add_argument("video")
    p.add_argument("--out", required=True, help="output directory for this video")
    p.set_defaults(func=_not_built(2, "inspect_vo/ingest.py"))

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
