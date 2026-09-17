# Repository reporting contract map

Use this as a navigation map, not a substitute for the repository. The repository evolves; confirm every mutable contract in the live files before acting.

## Authority order

1. Active user goal / explicit scope.
2. Applicable `CLAUDE.md` chain, followed by any repository-declared cross-tool `AGENTS.md` / `AGENTS.override.md` chain.
3. `ROADMAP.md` current frontier and acceptance criteria.
4. Active Phase 4 plan/decision documents under `docs/plans/`.
5. Implemented reporting code, tests, manifests, and exact upstream artifact contract consumed by the task.

When prose and executable behavior disagree, surface the conflict. Do not silently use this reference to choose a winner.

## Current reporting surface to inspect

- `reporting/claims/` — factual/interpretive claim model and validation.
- `reporting/charts/` — declarative chart specification and validation.
- `reporting/render/` — deterministic static renderer and accessibility checks.
- `reporting/package/` — approved handoff validation/building, package generation, input hash checks, review artifacts, package manifests.
- `tests/test_phase4.py` — executable Phase 4 acceptance behavior, including replay/offline/security/cross-phase fixtures.
- `docs/plans/phase-4-article-visualization-generation.md` — durable Phase 4 goals and boundaries.
- `docs/plans/phase-4-implementation-decisions.md` — resolved first-delivery implementation choices.
- `ROADMAP.md` — current Phase 4R frontier and later closure criteria.

Inspect any Phase 3 artifact writer/schema actually consumed by the reporting change. Do not duplicate its contract inside reporting.

## Stable architectural boundary

Phase 4 is a presentation/review layer over approved local research artifacts. It does not own:

- ingestion/provider access;
- backtest execution or metrics semantics;
- cohort construction, feature generation, labels, split logic, hypothesis testing, or candidate promotion;
- external publication.

Reporting may validate and present approved values, but it must not become a second analysis engine.

## Current implementation orientation (confirm before use)

At the time this skill was authored, the repository had already implemented:

- a hash-verified Phase 3 -> Phase 4 approved handoff;
- explicit approval metadata;
- staged artifact hash verification;
- factual claim evidence pointers with dataset/config/time-range checks;
- declarative static chart specs and SVG rendering;
- deterministic package IDs/artifact checksums;
- pending human-review output;
- secret/path scanning;
- offline end-to-end fixture coverage.

The active integrity gap was stronger proof that an emitted numeric/comparative value is actually *derived from* the referenced evidence, plus stricter chart transformation/annotation semantics. Treat that statement as historical orientation only; inspect `ROADMAP.md` for the current frontier.

## Neighbor routing

Do not activate this skill merely because reporting consumes data produced elsewhere.

- If the task changes Phase 3 research methodology, use research governance.
- If it changes Phase 2 execution/accounting/metrics, use backtest integrity.
- If it changes persistence, use storage migration.
- If it changes providers, use ingestion.
- If it posts/uploads/publishes, use an explicitly authorized external-effects workflow.
