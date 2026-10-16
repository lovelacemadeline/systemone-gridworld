---
type: guide
status: active
title: Documentation Conventions — the single source of truth for how we write docs
owner: systemone-gridworld
 # The AUTHORITATIVE machine-read vocabulary (docloom.toml: vocabulary.from-doc
 # points here). The prose tables below are agreement-checked against this
 # block — edit both together or `docloom check` fails. (Comments indented one
 # space: the frontmatter parser reads a line-leading `# ` as a Markdown
 # heading, i.e. a broken frontmatter fence.)
vocabulary:
  types:
    - prd
    - epic
    - story
    - register
    - decision
    - reference
    - guide
    - runbook
    - plan
    - research
    - snapshot
    - working-artifact
  statuses:
    - draft
    - active
    - superseded
    - parked
    - archived
    - snapshot
    - stub
    - temporary
  execution-statuses:
    - pending
    - ready-for-dev
    - in-progress
    - blocked
    - needs-refactoring
    - superseded
    - completed
    - deferred
  conditional:
    superseded: superseded-by
    stub: points-to
---

# Documentation Conventions

> **This is the canonical source of truth for how documentation works in
> `systemone-gridworld`.** Every `.md` file in this repo follows it. Before you create,
> rename, move, or re-purpose any document — read this. Do **not** invent a new
> doc "kind", status word, or ad-hoc label; if something doesn't fit, split it
> (§6), don't add a new type. Enforced by `docloom check` (pre-commit + CI).

## 1. Every doc carries two frontmatter fields

Two **orthogonal** required fields, both closed enums so they can be
machine-checked:

- **`type:`** — *what kind of thing this is.* One of the 12 values in §2.
  Immutable for the life of the doc.
- **`status:`** — *how much to trust it today.* One of the 8 values in §3.
  Changes over time.

"Archived", "parked", "superseded", "stub" are **statuses, not types and not
directories**. A document's **`type:` implies its home directory** (§2) —
directories are a *consequence* of type, so `docs/` never becomes a junk drawer.

## 2. The `type:` vocabulary (closed — 12 values)

| `type:` | What it is | Canonical home | Naming |
|---|---|---|---|
| `prd` | Product/feature requirements — the *what & why* | `docs/product/` | `prd-<slug>.md` |
| `epic` | One epic's scope + its story list | `docs/epics/` | `epic-NN.md` |
| `story` | One story spec + acceptance criteria | `docs/stories/` | `NN-Mx-<slug>.md` |
| `register` | **The citeable spine** — a canonical enumeration other docs cite by ID | `docs/reference/`, `docs/epics/index.md` | `<slug>-register.md` |
| `decision` | One ratified decision + provenance + rejected alternatives (ADR) | `docs/adr/` | `NNNN-<slug>.md` |
| `reference` | Evergreen *descriptive* fact: architecture, API, dataflow | `docs/reference/` | `<slug>.md` |
| `guide` | Prescriptive *how-to / conventions* (this file, dev setup, agent rules) | repo root + `docs/` | `<slug>.md` |
| `runbook` | Operational step-by-step: deploy, bring-up, recover | `docs/runbooks/` | `<slug>.md` |
| `plan` | Forward-looking roadmap **not yet decomposed into epics** | `docs/` | `NN-<slug>.md` |
| `research` | Time-boxed investigation — an *input*, never authoritative | `docs/research/` | `<slug>-YYYY-MM.md` |
| `snapshot` | True only *as of its date*: readiness reports, handovers | `docs/status/` | `<slug>-YYYY-MM-DD.md` |
| `working-artifact` | Temporary scaffolding; **deleted before merge** | anywhere | `<SLUG>-YYYY-MM-DD.md` |

## 3. The `status:` vocabulary (closed — 8 values)

| `status:` | Meaning | Conditional field |
|---|---|---|
| `draft` | Being written; not yet authoritative | — |
| `active` | Current and authoritative | — |
| `superseded` | Replaced; kept for history | **`superseded-by:`** (required) |
| `parked` | Real but paused; not being maintained | — |
| `archived` | Frozen historical record; do not update | — |
| `snapshot` | Point-in-time; never updated after its date | — |
| `stub` | Pointer to an upstream/canonical source | **`points-to:`** (required) |
| `temporary` | Scaffolding to be deleted before merge | — |

**`epic` / `story` use a second, closed status axis: execution state** —
`status:` on those two types means *how far the work has got*:

| execution `status:` | Meaning |
|---|---|
| `pending` | Outlined; detailed spec not yet written |
| `ready-for-dev` | Spec complete, not started |
| `in-progress` | Being implemented |
| `blocked` | Cannot proceed (dependency/issue) |
| `needs-refactoring` | Code exists but needs rework |
| `superseded` | Replaced or absorbed elsewhere |
| `completed` | Built and tested |
| `deferred` | Intentionally postponed |

## 4. The frontmatter contract

```yaml
---
type: story               # one of the 12 (§2)
status: in-progress       # lifecycle (§3) or execution state for epic/story
title: Human-readable title
owner: <name>
updated: YYYY-MM-DD       # last meaningful review date — not git noise
# conditional:
superseded-by: <path>     # required iff status: superseded
points-to: <url|path>     # required iff status: stub
shape-exempt: <reason>    # epic only — opts out of the epic line ceiling (§5.3);
                          # the reason is printed by `docloom check`
---
```

## 5. Sub-conventions

### 5.1 `register` — cite by ID, never restate
A register *owns* a set of facts (epic numbers, requirement clauses, versions).
Everything else **cites it by ID** rather than copying the value — duplicated
facts are how drift starts. A **clause register** (owning an id family like
`C-CORE-*`) declares a machine-readable `register:` frontmatter block; the
checker discovers every such doc and runs the same generic checks over each —
adding a register is *adding a conforming doc*, never a checker edit:

```yaml
register:
  name: core                          # label used in check messages
  clause-prefixes: [C-CORE]           # required — id families this register owns
  crosscutting-prefixes: [NFR-CORE]   # optional — resolve-only (no orphan/coverage)
  enactable-glyphs: ["🔴", "🟡", "🟢"] # optional — glyphs marking real work
  proposed: []                        # optional — pending ids, exempt from checks
  owner-map:                          # optional — enables completion-coverage
    heading: "### Coverage Map"
    until: "## Notes"
    line: '- \*\*Epic (\d+):\*\*'
```

Body format the parser reads: each clause on its own line as
`- **<ID>** <glyphs> — <description>`.

**Every** `type: register` doc must declare its id space — a hard check. Either
name the prefixes it owns (`clause-prefixes:`), or state that it owns none:

```yaml
register:
  owns-no-clause-ids: epic numbers — enforced by the epic-number identity check
```

The reason must say where its ids *are* enforced, if anywhere. A citeable id
kind (the leading token, e.g. `C` in `C-CORE-1`) must also be listed under
`[docloom.id-kinds]` for the unowned-family advisory to see it.

### 5.2 `decision` — ADRs live in `docs/adr/`
Numbered `NNNN-<slug>.md`; allocate from the ledger in `docs/adr/index.md`.
Upstream decisions get a local `status: stub` pointer so every `ADR-NNNN`
citation resolves to a real local file.

### 5.3 `epic` — unique number, stories in their own files
Every epic doc carries `epic: N` matching its `epic-NN.md` filename; allocate
numbers from the registry in `docs/epics/index.md`. Each story gets its own
file under `docs/stories/` (`NN-Mx-<slug>.md`, `type: story`); the epic keeps
only a high-level `## Stories` table. When you add a story, add its tracker row
in the same change (§7).

**Epics stay thin.** An epic is a *pointer and a scope statement*, not a findings
document: frontmatter, a scope paragraph, an optional design-provenance note, the
`## Stories` table, at most one screen of current-state summary, and cross-links.
Findings live in the stories that produced them; the epic cites them (§5.1 —
duplicated facts are how drift starts, and a shadow copy of story results is the
worst case of it, because it reads plausibly while silently going stale). The
checker's epic-shape sub-checks make this mechanical — as shipped:

- **E1 — no result sections.** No heading matching
  `^#+\s*(\w+\s+)?(Result|Results|Findings|Measurements|Outcome)s?\b`. The one
  optional leading word is deliberate: `## Epic outcome — FINAL v3` is the shape
  these sections actually take, and an anchored match would miss every one of
  them. Exactly one word — two or more before the noun is prose, not a section
  label (`## How we measure results` is fine).
- **E2 — no measured-number tables outside the `## Stories` table.** No cell in
  any other table may hold a measurement literal
  (`\d+(\.\d+)?\s*(tok/s|GB/s|GiB|GB|MB|ms|s|x)\b` or `\d+(\.\d+)?\s*[%×]` —
  longest unit first because regex alternation is first-match, and `%`/`×` split
  out because `\b` after a non-word character never fires on `50%.`). Deliberately
  narrow: prose numbers are allowed, tables are not — tables are what accrete.
- **E3 — a soft line ceiling** over the whole file, frontmatter and `## Stories`
  table included. A legitimately long epic declares `shape-exempt: <reason>` in
  its frontmatter (§4): one human-written line, printed on every check run so it
  gets reviewed rather than silently inherited. **A bare `shape-exempt:` with no
  reason grants nothing** — the escape hatch is held to the standard it grants,
  the same way `conventions-exempt` is (§7).
- **E4 — quantitative claims cite a story.** A paragraph carrying a measurement
  literal should also link a story or epic doc. **Advisory permanently, never
  enforced**: the false-positive rate on prose numbers (versions, model sizes,
  dates) is high enough that enforcing it would train people to ignore the check,
  which is how a lint dies. Its job is to make the current-state summary
  self-auditing — a number with no story behind it is either a missing story or
  the epic's own invention.

E1-E3 roll out on a ratchet (`[docloom.epic_shape] enforced` in `docloom.toml`,
default `false` = report as *would fail once enforced*), exactly as Gate 3's
anchors do.

## 6. Allocating a new document
1. Pick the `type:` from §2. If nothing fits, the doc is probably **two types
   fused** — split it. Don't add a 13th type without changing this doc first.
2. Put it in the type's canonical home; give it the frontmatter contract (§4).
3. Stories and ADRs move together with their registries (§7).

## 7. Enforcement — three gates (`docloom check`)

Three gates, each aggregating sub-checks:

- **Gate 1 — Doc validity**: is each doc well-formed on its own? (typed,
  statused, real YAML, resolving links — and this doc's own vocabulary tables
  agreeing with its `vocabulary:` block.)
- **Gate 2 — Consistency & tracking**: do the epic docs, story files, sprint
  tracker, and registers agree with each other? (number identity, the
  tracker↔file bijection, citation resolution, orphan + coverage checks.)
- **Gate 3 — Spec-grounding anchors**: do stories name code that exists?

**The authoritative sub-check list is `docloom check`'s own output** — it
enumerates every gate and sub-check for the installed docloom version on every
run. This doc deliberately does not restate that list: it would go stale on
every docloom upgrade, and drift-by-restatement is the disease this whole
system exists to cure (§5.1 applies to us too).

**Gate 3 in practice**: every in-scope story carries an `anchor:`
list — concrete code artifacts whose existence is checked mechanically — or the
explicit opt-out `anchor: none  # <reason>`:

```yaml
anchor:
  - symbol: "src/pkg/module.py::ClassName"       # dotted ::Class.method ok
  - test:   "tests/test_module.py::test_invariant"
  - route:  "GET /api/v1/things"
```

> **Anchors are a tripwire for *absence*, never a proof of *done*.** A
> `completed` story whose anchors don't all resolve is a hard fail — the
> "marked done, but the named thing isn't there" lie. Semantic correctness
> stays with the test suite.

**The enforced-interim pattern**: when a story ships a stopgap for work another
story owns, don't leave a bare TODO — add a *target* anchor (the test that only
passes once the stopgap is gone) to the story that owns the real
implementation, and note the seam where the interim lives. The owning story
then can't reach `completed` while the stopgap survives.
