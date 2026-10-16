"""``gridworld`` command line: ``view`` a recorded episode, ``oracle`` to record one.

``play`` (backends, scoring) arrives with Epic 4.
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence

__all__ = ["main"]


def _view(args: argparse.Namespace) -> int:
    from .view import ViewUnavailable, play_file

    try:
        shown = play_file(
            args.episode,
            fps=args.fps,
            tile=args.tile,
            scale=args.scale,
            verify=not args.no_verify,
            hold=not args.no_hold,
        )
    except ViewUnavailable as exc:
        print(f"gridworld view: {exc}", file=sys.stderr)
        return 2
    print(f"{args.episode}: {shown} frames")
    return 0


def _oracle(args: argparse.Namespace) -> int:
    from .record import record_episode
    from .sim import WorldConfig

    result = record_episode(
        args.out, args.seed, WorldConfig(), backend="oracle", mode="observation"
    )
    print(f"{args.out}: seed {args.seed}, {result.observation.tick} ticks, {result.info['reason']}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="gridworld", description=__doc__.split("\n")[0])
    sub = parser.add_subparsers(dest="command", required=True)

    view = sub.add_parser("view", help="play a recorded episode (.jsonl) in a window")
    view.add_argument("episode")
    view.add_argument("--fps", type=float, default=4.0, help="ticks per second (0 = unthrottled)")
    view.add_argument("--tile", type=int, default=16)
    view.add_argument("--scale", type=int, default=3)
    view.add_argument("--no-verify", action="store_true", help="skip re-stepping the sim first")
    view.add_argument("--no-hold", action="store_true", help="close when the episode ends")
    view.set_defaults(func=_view)

    orc = sub.add_parser("oracle", help="record one oracle-played episode (for the viewer)")
    orc.add_argument("--seed", type=int, default=0)
    orc.add_argument("--out", required=True)
    orc.set_defaults(func=_oracle)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
