---
type: register
status: active
register:
  owns-no-clause-ids: ADR numbers, not clause ids; every ADR-NNNN citation is resolved by globbing the ADR directory
title: ADR Ledger
---

# ADR Ledger

Allocate the next ADR number here before creating `NNNN-<slug>.md`. Upstream
decisions get a local `status: stub` pointer so every `ADR-NNNN` citation
resolves locally.

| ADR | Title | Status | Local/Upstream |
|---|---|---|---|
| ADR-0001 | [One observation, many renderers](0001-one-observation-many-renderers.md) | active | local |
| ADR-0002 | [Backends speak the wire schema only](0002-backends-speak-the-wire-schema-only.md) | active | local |
