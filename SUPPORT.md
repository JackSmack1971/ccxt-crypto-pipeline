# Support

`ccxt-crypto-pipeline` is a local-first research repository, not a hosted
service or managed trading platform. Support is provided through the
repository’s checked-in documentation and GitHub Issues among repository
collaborators. There is no dedicated support team, public forum, guaranteed
response-time SLA, or production operations desk.

## Start with the repository documentation

Use the source that matches the question:

1. [`README.md`](README.md) — installation, commands, configuration overview,
   architecture summary, and common troubleshooting.
2. [`docs/RUNBOOK.md`](docs/RUNBOOK.md) — local setup, provider configuration,
   one-pass jobs, scheduler operations, monitoring, and debugging.
3. [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) — module boundaries, provider
   routing, canonical storage, schema, and current phase boundaries.
4. [`CONTRIBUTING.md`](CONTRIBUTING.md) — development workflow, tests, schema
   changes, provider changes, and pull-request expectations.
5. [`SECURITY.md`](SECURITY.md) — vulnerability reporting, secret exposure, and
   authorized security testing.
6. The applicable specification under [`docs/plans/`](docs/plans/) — phase
   acceptance criteria and unresolved design decisions.

The implemented code, tests, storage contracts, and active phase requirements
take precedence over stale examples or aspirational design text. If
documentation and behavior disagree, open an issue describing the exact
discrepancy rather than silently relying on one of them.

## Before opening an issue

Confirm that the question is not answered by the documentation, then collect a
minimal sanitized reproduction. Include:

- the commit or branch, operating system, and Python version;
- installation method and relevant dependency versions;
- the exact command or Python entry point used;
- whether the run was offline/fixture-only or used live providers;
- the configured phase, component, provider, chain/exchange, and database path
  type (do not include secret-bearing paths or URLs);
- the expected behavior and the observed behavior;
- the complete non-sensitive error and relevant logs;
- the smallest fixture, schema, or configuration excerpt that reproduces it.

Do not attach `.env`, API keys, bearer tokens, passwords, wallet material,
secret-bearing RPC URLs, live DuckDB/Parquet data, private provider responses,
or unreviewed generated research packages. Redact credentials and personal or
commercially sensitive data before posting. A suspected vulnerability or secret
exposure must be reported privately using [`SECURITY.md`](SECURITY.md), never in
a public issue.

## GitHub Issues

GitHub Issues are the repository’s supported channel for non-sensitive support
questions, reproducible bugs, documentation corrections, and scoped feature or
design discussion. GitHub Discussions are currently disabled; use an Issue and
keep the conversation focused on one problem or proposal.

Choose a useful title and prefix it when helpful:

- `[Support]` — a usage or setup question;
- `[Bug]` — behavior that contradicts documented or tested behavior;
- `[Data quality]` — missing, duplicated, late, malformed, or inconsistent
  observations;
- `[Provider]` — an ingestion adapter, capability, rate-limit, or upstream
  contract issue;
- `[Research]` — a temporal, leakage, provenance, metric, or reporting concern;
- `[Docs]` — an incorrect or incomplete repository instruction;
- `[Feature]` — a proposed change with a concrete use case and boundary.

One issue should describe one primary problem. Maintainers may ask for a
minimal fixture, reproduce the issue locally, request documentation updates, or
close a duplicate, unsupported, unactionable, or out-of-scope report.

### Issue template for support questions

```text
## Summary

## Environment
- Commit/branch:
- OS:
- Python:
- Install method:
- Provider/chain/exchange (if applicable):
- Offline fixture or live provider:

## Command or entry point

## Expected behavior

## Observed behavior

## Sanitized error/log output

## Minimal reproduction or relevant configuration
```

For a bug, add the smallest deterministic test or fixture when practical. For a
feature or design proposal, explain the use case, affected phase, architectural
boundary, acceptance behavior, reproducibility impact, and why existing code
cannot satisfy it.

## What support covers

Maintainers can help clarify or triage:

- documented local installation and command behavior;
- configuration and scheduler operation within the checked-in contracts;
- reproducible bugs in the implemented ingestion, storage, normalization,
  analysis, or reporting paths;
- data-quality and provenance discrepancies supported by local fixtures or
  persisted evidence;
- documentation errors and narrowly scoped design questions.

## What support does not provide

This repository does not provide:

- exchange, RPC, explorer, aggregator, or Solana provider customer support;
- provider credentials, paid-tier access, rate-limit exceptions, or hosted
  infrastructure;
- recovery of deleted local databases, Parquet data, credentials, or wallets;
- investment, trading, profitability, or predictive-alpha advice;
- live or paper trading, transaction signing, wallet custody, or execution
  support;
- unauthorized testing of third-party systems;
- custom private pipelines or operational guarantees for production workloads.

Provider outages, upstream schema changes, rate limits, stale observations, and
unsupported capabilities should be identified as such. A provider limitation
is not a repository defect unless the repository misrepresents, mishandles, or
silently launders that limitation into a different value.

## Response and resolution expectations

There is no guaranteed response time. Maintainers prioritize security reports
through the private process in [`SECURITY.md`](SECURITY.md), then reproducible
regressions and data-integrity issues, followed by documentation corrections,
scoped support questions, and feature proposals.

An issue may be closed when it is resolved by a merged change, answered by
existing documentation, superseded by an authoritative design decision, not
reproducible with the supplied evidence, dependent on an unavailable external
provider, or outside the project’s scope. Closed issues may be reopened when
new, concrete evidence shows that the original conclusion no longer holds.

Please keep issue discussions respectful, concise, and focused on evidence.
