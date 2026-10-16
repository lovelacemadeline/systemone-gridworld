"""``gridworld`` command line: ``play`` a backend, ``view`` a recorded episode, ``oracle``.

``gridworld play --backend fake|local|http --mode text|image --memory ... --episodes N``
runs a session (``--episodes 0`` = until Esc/q or Ctrl-C) and writes the
report under ``--out`` (default ``runs/``). World flags (``--width``,
``--height``, ``--monsters``, ``--walls``, ``--hp``, ``--tick-limit``) default to
:class:`~gridworld.sim.WorldConfig`'s defaults.
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


def _backend(args: argparse.Namespace):
    from .backends import make_backend

    if args.backend == "fake":
        return make_backend("fake", noise=args.noise, latency_s=args.latency, seed=args.seed)
    if args.backend == "local":
        kw = {"int8": args.int8}
        if args.model:
            kw["model"] = args.model
        return make_backend("local", **kw)
    return make_backend("http", base_url=args.url, timeout=args.timeout)


def _play(args: argparse.Namespace) -> int:
    from .harness.prompts import load_prefix
    from .harness.report import headline_table
    from .harness.session import run_session
    from .sim import WorldConfig

    view = None
    if args.view:
        from .view import LiveView, ViewUnavailable

        try:
            view = LiveView(fps=args.fps, scale=args.scale, caption="gridworld play")
        except ViewUnavailable as exc:
            print(f"gridworld play --view: {exc}", file=sys.stderr)
            return 2
    defaults = WorldConfig()
    config = WorldConfig(
        width=args.width or defaults.width,
        height=args.height or defaults.height,
        n_monsters=defaults.n_monsters if args.monsters is None else args.monsters,
        wall_density=defaults.wall_density if args.walls is None else args.walls,
        player_hp=args.hp or defaults.player_hp,
        tick_limit=args.tick_limit or defaults.tick_limit,
    )
    backend = _backend(args)
    try:
        result = run_session(
            backend,
            mode=args.mode,
            memory=args.memory,
            prefix=load_prefix(args.prefix),
            episodes=args.episodes,
            seed=args.seed,
            out_dir=args.out,
            config=config,
            view=view,
            max_ticks=args.max_ticks,
            flash_s=args.flash,
            legal_only=args.legal_only,
            labels=args.labels,
        )
    finally:
        if view is not None:
            view.close()
    print(headline_table(result.report.summary))
    print(f"report: {result.md}\n        {result.json}\nepisodes: {result.episode_dir}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    from .harness.memory import MEMORY_MODES

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

    play = sub.add_parser("play", help="run a backend for N episodes and write a report")
    play.add_argument("--backend", choices=["fake", "local", "http"], default="fake")
    play.add_argument("--mode", choices=["text", "image"], default="text")
    play.add_argument("--memory", choices=sorted(MEMORY_MODES), default="none")
    play.add_argument("--episodes", type=int, default=5, help="0 = until stopped (Esc/q, Ctrl-C)")
    play.add_argument("--seed", type=int, default=0, help="first seed; episode i uses seed + i")
    play.add_argument("--max-ticks", type=int, default=None, help="cut episodes short")
    play.add_argument(
        "--legal-only", action="store_true", help="offer only actions that do something"
    )
    play.add_argument(
        "--labels",
        choices=["letters", "words"],
        default="letters",
        help="answer labels: A-F letters (default) or the action words (options.label_style)",
    )
    play.add_argument("--prefix", default=None, help="file replacing the default rules prefix")
    play.add_argument("--out", default="runs")
    play.add_argument("--view", action="store_true", help="watch in a window (needs [view])")
    play.add_argument("--fps", type=float, default=0.0, help="cap ticks per second in the view")
    play.add_argument("--scale", type=int, default=3)
    play.add_argument("--flash", type=float, default=1.0, help="seconds to show each result")
    world = play.add_argument_group("world (defaults: WorldConfig)")
    world.add_argument("--width", type=int)
    world.add_argument("--height", type=int)
    world.add_argument("--monsters", type=int)
    world.add_argument("--walls", type=float, help="wall density")
    world.add_argument("--hp", type=int, help="player hp")
    world.add_argument("--tick-limit", type=int)
    be = play.add_argument_group("backend options")
    be.add_argument("--noise", type=float, default=0.0, help="fake: random-action rate")
    be.add_argument("--latency", type=float, default=0.0, help="fake: seconds per call")
    be.add_argument("--model", default=None, help="local: mlx-lm repo")
    be.add_argument("--int8", action="store_true", help="local: W8A8 kernels (M5 only)")
    be.add_argument("--url", default="http://127.0.0.1:8080", help="http: server base URL")
    be.add_argument("--timeout", type=float, default=30.0, help="http: seconds")
    play.set_defaults(func=_play)

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
