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


def _think_kwargs(args: argparse.Namespace) -> dict:
    return {
        "trigger": args.think,
        "style": args.plan,
        "max_tokens": args.plan_max_tokens,
        "threshold": args.think_threshold,
        "cooldown": args.think_cooldown,
        "cost": args.think_cost,
        "replan_every": args.replan_every,
        "replan_on_damage": args.replan_on_damage,
        "replan_on_reversals": args.replan_on_reversals,
        "plan_persist": args.plan_persist,
        "route_deviation_limit": args.route_deviation_limit,
    }


def _planner(args: argparse.Namespace, backend):
    """The planner: ``--plan-backend`` (default: the decision backend's kind), with
    ``--plan-model`` loading a second local model and ``--plan-url`` a second server."""
    from .harness.plan import FakePlanner, HTTPPlanner, LocalPlanner

    kind = args.plan_backend or args.backend
    if kind == "http":
        return HTTPPlanner(args.plan_url or args.url)
    if kind == "local":
        if args.plan_model:
            return LocalPlanner.from_repo(args.plan_model)
        if args.backend != "local":
            raise SystemExit("--plan-backend local needs --plan-model unless --backend is local")
        return LocalPlanner.from_backend(backend)
    return FakePlanner()


def _check_plan_flags(args: argparse.Namespace) -> str | None:
    kind = args.plan_backend or args.backend
    if args.plan_model and kind != "local":
        return "--plan-model needs a local planner (--backend local or --plan-backend local)"
    if args.plan_url and kind != "http":
        return "--plan-url needs --plan-backend http"
    return None


def _play(args: argparse.Namespace) -> int:
    from .harness.prompts import load_prefix
    from .harness.report import headline_table
    from .harness.session import run_session
    from .harness.think import ThinkConfig
    from .sim import WorldConfig

    try:
        think = ThinkConfig(**_think_kwargs(args))
    except ValueError as exc:
        print(f"gridworld play: {exc}", file=sys.stderr)
        return 2
    problem = _check_plan_flags(args)
    if problem:
        print(f"gridworld play: {problem}", file=sys.stderr)
        return 2
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
    planner = _planner(args, backend) if think.trigger != "never" else None
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
            think=think,
            planner=planner,
            memory_k=args.memory_k,
            memory_visits=args.memory_visits,
        )
    finally:
        if view is not None:
            view.close()
    print(headline_table(result.report.summary))
    print(f"report: {result.md}\n        {result.json}\nepisodes: {result.episode_dir}")
    return 0


def _compare(args: argparse.Namespace) -> int:
    from pathlib import Path

    from .harness.report import RunReport, comparison_table

    reports = [RunReport.model_validate_json(Path(p).read_text()) for p in args.reports]
    print(comparison_table(reports))
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
    play.add_argument("--memory-k", type=int, default=3, help="summary: recent actions kept")
    play.add_argument(
        "--memory-visits", action="store_true", help="summary: add visit counts to the tail"
    )
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
    two = play.add_argument_group("System Two (Epic 5)")
    two.add_argument(
        "--think",
        choices=["never", "start", "demand", "action", "rule"],
        default="never",
        help="action: plan is a seventh option of the action question (story 5.7)",
    )
    two.add_argument("--replan-every", type=int, default=None, help="rule: plan every N ticks")
    two.add_argument("--replan-on-damage", action="store_true", help="rule: plan when hp drops")
    two.add_argument(
        "--replan-on-reversals", type=int, default=None, help="rule: plan after K reversals"
    )
    two.add_argument(
        "--think-threshold", type=float, default=0.7, help="demand: P(yes) that triggers a plan"
    )
    two.add_argument("--think-cooldown", type=int, default=5, help="min ticks between plans")
    two.add_argument(
        "--think-cost",
        choices=["free", "tick"],
        default="free",
        help="free: plan before acting; tick: planning spends the turn as wait",
    )
    two.add_argument("--plan", choices=["direct", "trace"], default="direct")
    two.add_argument(
        "--plan-persist",
        action="store_true",
        help="keep the whole plan in the tail until replaced (pre-5.8; default: consume the route)",
    )
    two.add_argument(
        "--route-deviation-limit",
        type=int,
        default=2,
        help="drop the plan after this many consecutive moves off its route",
    )
    two.add_argument("--plan-max-tokens", type=int, default=4096)
    two.add_argument(
        "--plan-backend",
        choices=["local", "http", "fake"],
        default=None,
        help="where plans run (default: the decision backend's kind)",
    )
    two.add_argument("--plan-model", default=None, help="local: a second model for plans")
    two.add_argument("--plan-url", default=None, help="http: a separate server for plans")
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

    cmp_ = sub.add_parser("compare", help="one quality-versus-cost table across run reports")
    cmp_.add_argument("reports", nargs="+", help="run report .json files")
    cmp_.set_defaults(func=_compare)

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
