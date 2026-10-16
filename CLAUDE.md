---
type: guide
status: active
title: Claude Code Project Instructions — systemone-gridworld
---

# Claude Code Project Instructions

## Documentation — docloom

All documentation in this repo follows [`docs/doc-conventions.md`](docs/doc-conventions.md)
— read it before you create, move, rename, or re-purpose any `.md` file.
Enforced by `docloom check` (pre-commit + CI):

- Every doc carries `type:` (12 closed values) and `status:` (8 closed values);
  a doc's type determines its home directory. **Never invent a new kind,
  status word, or ad-hoc label.**
- Stories live in `docs/stories/` with a matching row in
  `docs/sprint-status.yaml` (bijection-checked) and an `anchor:` list grounding
  them in real symbols/tests/routes.
- To record finished or discussed work as docs, use the `docloom` skill
  (`.claude/skills/docloom/SKILL.md`).
- Run `docloom check` before committing doc changes.
