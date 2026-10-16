"""Story 4.5 — legal-action mask and label style."""

from __future__ import annotations

import json

import pytest
from jsonschema import Draft202012Validator
from test_roundtrip import episode_observations

from gridworld import cli
from gridworld.backends import BackendError, build_request, call
from gridworld.backends.fake import FakeBackend
from gridworld.backends.schema import load_schema, validate_request
from gridworld.harness import run_episode
from gridworld.record import read_episode
from gridworld.sim import Action, GridWorld, generate_map, legal_actions


def effect(world: GridWorld, obs, action: Action) -> bool:
    world.load(obs)
    after = world.step(action).observation
    hp = lambda o: sum(m.hp for m in o.monsters)
    return after.player != obs.player or hp(after) < hp(obs)


def test_legal_actions_match_step_on_200_seeds():
    world = GridWorld()
    checked = 0
    for seed in range(200):
        for obs in episode_observations(seed, noise=0.3)[:-1]:
            legal = legal_actions(obs)
            for a in Action:
                assert (a in legal) == (a is Action.WAIT or effect(world, obs, a)), (
                    seed,
                    obs.tick,
                    a,
                )
                checked += 1
    assert checked > 10_000


def test_legal_actions_order_and_attack(make_obs):
    obs = make_obs(player=(0, 0), walls=[(1, 0)], monsters=[((0, 1), 2)])
    assert legal_actions(obs) == (Action.ATTACK, Action.WAIT)
    assert legal_actions(make_obs(player=(2, 2))) == (*list(Action)[:4], Action.WAIT)


def test_legal_only_request_offers_the_legal_set_on_the_vendored_schema(make_obs):
    obs = make_obs(player=(0, 0), monsters=[((1, 0), 2)])
    built = build_request(obs, legal_only=True)
    assert list(built.request["questions"]["action"]["criteria"]) == ["south", "attack", "wait"]
    assert built.offered == (Action.SOUTH, Action.ATTACK, Action.WAIT)
    assert Draft202012Validator(load_schema("request")).is_valid(built.request)
    assert build_request(obs).offered == tuple(Action)


def test_label_style_words_needs_the_local_extension():
    built = build_request(generate_map(3), label_style="option-text")
    assert built.request["options"] == {"label_style": "option-text"}
    validate_request(built.request)
    assert not Draft202012Validator(load_schema("request")).is_valid(built.request)
    assert "options" not in build_request(generate_map(3), label_style="letters").request
    bad = build_request(generate_map(3)).request | {"options": {"label_style": "emoji"}}
    with pytest.raises(ValueError, match="label_style"):
        validate_request(bad)


def test_adapter_rejects_a_choice_outside_the_offered_set(make_obs):
    obs = make_obs(player=(0, 0), monsters=[((1, 0), 2)])
    req = build_request(obs, legal_only=True).request

    class North:
        id = "north"

        def decide(self, request):
            probs = {o: 1 / 3 for o in request["questions"]["action"]["criteria"]}
            return {
                "model": "x",
                "answers": {
                    "action": {
                        "type": "choice",
                        "choice": "north",
                        "probabilities": probs,
                        "confidence": 0.4,
                    }
                },
                "usage": {"input_tokens": 1, "output_tokens": 0},
            }

    with pytest.raises(BackendError, match="not one of"):
        call(North(), req)


def test_legal_only_episode_records_offered_and_keeps_agreement(tmp_path):
    path = tmp_path / "ep.jsonl"
    s = run_episode(GridWorld(), FakeBackend(), seed=3, record_path=path, legal_only=True)
    assert s.agreement == 1.0 and s.mean_options_offered < 6
    ticks = read_episode(path).ticks
    assert all(
        t.offered and t.action in t.offered and set(t.probabilities) == set(t.offered)
        for t in ticks
    )


def test_cli_flags_reach_the_report(tmp_path):
    out = tmp_path / "runs"
    argv = ["play", "--episodes", "2", "--out", str(out), "--legal-only", "--labels", "words"]
    assert cli.main(argv) == 0
    (js,) = out.glob("*.json")
    data = json.loads(js.read_text())
    assert data["meta"]["legal_only"] is True and data["meta"]["labels"] == "words"
    assert js.name.endswith("-text-none-legal-words.json")
    assert data["summary"]["mean_options_offered"] < 6


def test_local_backend_refuses_label_style_until_upstream_supports_it():
    pytest.importorskip("mlx_classifiers")
    from mlx_classifiers.fitting import CalibrationConfig
    from mlx_classifiers.runner import FakeRunner
    from mlx_classifiers.schema import RequestOptions

    from gridworld.backends.local import LocalBackend

    if "label_style" in RequestOptions.model_fields:
        pytest.skip("installed mlx-classifiers supports label_style")
    backend = LocalBackend(runner=FakeRunner(), calibration=CalibrationConfig())
    with pytest.raises(NotImplementedError, match="label_style"):
        backend.decide(build_request(generate_map(3), label_style="option-text").request)


@pytest.mark.xfail(strict=True, reason="re-vendor pending: upstream schema lacks label_style")
def test_vendored_schema_defines_label_style():
    """Target anchor (story 4.5): passes once schema/ is re-vendored with label_style.

    Strict xfail, so the re-vendor turns this into a failure until the local
    label_style extension (backends/schema.py, schema/local-extensions.md) is
    removed along with this marker.
    """
    assert "label_style" in load_schema("request")["$defs"]["RequestOptions"]["properties"]
