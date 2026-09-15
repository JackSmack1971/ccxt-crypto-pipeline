# AGENTS.md

## Purpose and scope

Applies to all of `reporting/`: `claims/`, `charts/`, `render/`, and `package/`.

Reporting is presentation-only. It consumes immutable approved local research evidence and produces deterministic review packages. It MUST NOT recompute upstream research semantics or publish externally.

Use `.agents/skills/evidence-bound-reporting/` for changes to handoffs, claims, charts, rendering, or package generation.

## Approved input boundary

Package generation MUST accept only the current repository-approved immutable handoff with required approval/reviewer metadata.

Every referenced research manifest and staged artifact MUST pass the implemented path and SHA-256 verification before use.

Input/output paths MUST remain sandboxed. Reject absolute paths, traversal, and any resolved path escaping the declared root.

Reporting MUST NOT mutate upstream research artifacts.

## Claims

Every factual numeric or comparative claim MUST resolve to approved staged evidence and a supported typed derivation.

The rendered value, units, formatting, comparison direction, dataset/query identity, and time range MUST agree with the validated derivation.

Reject missing/ambiguous rows, unsupported operations, incompatible units, non-finite values, invalid denominator behavior, or prose that disagrees with the derivation.

Keep interpretation distinct from fact. Interpretation MUST NOT introduce undeclared numeric/comparative facts.

## Charts and rendering

Chart specs MUST reference approved staged columns and declare units, provenance/source, meaningful accessibility text, and explicit missing-data behavior.

Only transformations explicitly approved by the upstream research result may run. A manifest MUST NOT self-authorize a transformation.

Do not silently fabricate zero, interpolate, drop, or relabel unavailable values.

Rendered SVG MUST continue to pass the repository accessibility validator and deterministic rendering expectations.

Do not infer support for a transformation/annotation merely because a lower-level validator happens to contain implementation code; follow the current approved reporting contract.

## Security and review state

Reporting MUST remain offline. Do not import/call ingestion or provider/network clients.

Generated packages MUST preserve secret-bearing URL/credential and unintended-local-path scanning.

An existing immutable package identity with different bytes is a conflict; NEVER overwrite it silently.

Generated output remains pending human review / approval-required. Generation MUST NOT mark its own output as published or externally approved.

External publication/distribution is outside this repository's implemented boundary.

## Change boundaries

MUST NOT recompute Phase 2 metrics, Phase 3 cohorts/features/labels/splits/promotion, or experiment statistics inside reporting.

MUST NOT weaken hash, approval, derivation, accessibility, offline, security, determinism, or review-state validation to make a package generate.

## Testing requirements

Run:

```bash
python -m pytest tests/test_phase4.py
```

For reporting code changes, also run the repository Skill guard when applicable:

```bash
python .agents/skills/evidence-bound-reporting/scripts/reporting_guard.py --repo .
```

Use `--package <path>` when a generated package is safely available and the Skill supports that check.

Behavioral changes MUST include fail-closed tests for the dangerous mismatch they could introduce: hash/path mismatch, unsupported derivation/transform, missing evidence, accessibility failure, secret/path leak, network access, or immutable overwrite.

## Completion criteria

A reporting change is complete only when approved input verification, claim/chart provenance, deterministic rendering, accessibility, security scanning, immutable output, pending-review state, focused tests, and applicable broader repository gates all pass.
