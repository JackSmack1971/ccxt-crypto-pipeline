# Contributing

Thank you for contributing to `ccxt-crypto-pipeline`. This repository is a
local-first crypto quantitative research system built on a provider-facing
ingestion pipeline. Contributions must
preserve reproducibility, point-in-time correctness, canonical asset identity,
and the separation between provider-facing ingestion and offline analysis.

## Before you start

Read these documents in order:

1. [`AGENTS.md`](AGENTS.md) — repository-wide constraints and phase gates.
2. [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) — module boundaries,
   persistence, provider routing, and current implementation status.
3. [`docs/RUNBOOK.md`](docs/RUNBOOK.md) — setup and operational commands.
4. The active phase specification under [`docs/plans/`](docs/plans/).

The implemented code, tests, storage contracts, and active user/phase
requirements are authoritative over stale planning text. If they conflict,
describe the conflict in the issue or pull request; do not silently redefine a
contract.

## Scope and architectural boundaries

The phases are deliberately separated:

- **Ingestion** is the only layer allowed to call exchanges, aggregators,
  explorers, RPC endpoints, Solana providers, or other external APIs.
- **Analysis and reporting** consume local DuckDB/Parquet or approved local
  artifacts and must run without live provider access.
- **Phase 2** owns simulation timing, execution assumptions, portfolio
  accounting, metrics, and run provenance.
- **Phase 3** owns cohorts, temporal features, labels, leakage controls,
  candidate evaluation, and research provenance.
- **Phase 4** is a presentation layer over approved results; it must not
  recompute research semantics or publish externally.

Do not add live or paper trading, automated execution, paid-data fallbacks,
strategy optimization, unsupported risk values, predictive-alpha claims, or
external publishing without an explicitly approved design change.

Preserve these invariants in every layer:

- A decision may use only observations available at or before its decision time.
- Missing or unsupported values stay missing or unsupported; do not fabricate,
  forward-fill across semantic boundaries, or silently substitute providers.
- EVM, Solana, DEX, and CEX identities remain address/exchange scoped. Symbol
  text alone is not a valid identity key.
- Deterministic ordering, configuration identity, dataset identity, time range,
  and upstream lineage must be retained wherever they affect reproducibility.
- Raw Phase 1 rows are read-only to analysis and reporting.

## Local setup

Use Python 3.10 or newer from the repository root:

```powershell
python -m pip install -e .
Copy-Item .env.example .env
python -m storage storage/pipeline.duckdb
```

Only configure credentials for the provider path you are intentionally running.
Never commit `.env`, provider credentials, secret-bearing RPC URLs, DuckDB
files, Parquet data, or generated local run data. The repository `.gitignore`
contains the baseline exclusions, but inspect `git status` before committing.

For repeatable dependency resolution, use the checked-in `uv.lock` with `uv`.

## Development workflow

1. Open or update an issue describing the problem, phase, affected boundary,
   acceptance behavior, and any unresolved design decision.
2. Create a focused branch from `main`. Prefer names such as
   `fix/<short-description>`, `feature/<short-description>`, or
   `docs/<short-description>`.
3. Select the smallest coherent implementation slice. Reuse existing storage,
   normalization, configuration, and test seams before adding abstractions or
   dependencies.
4. Keep provider changes inside ingestion adapters. Keep schema changes inside
   the canonical storage boundary. Do not mix unrelated cleanup into the same
   pull request.
5. Add or update behavior-focused tests before claiming the slice is complete.
6. Run the applicable checks below and record exact commands and outcomes.
7. Open a pull request for review. Do not push directly to `main` as a normal
   development workflow.

## Verification requirements

The baseline repository check is:

```powershell
python -m pytest
```

If the default interpreter is not the provisioned project interpreter, use
`./scripts/run-tests`. The wrapper prefers the project virtual environment. In managed workspaces
where project dependencies are already present in `.venv` but `pytest` is
provided by the host interpreter, it combines those two existing environments
without downloading packages. Arguments are passed through, so a focused,
quiet run is `./scripts/run-tests tests/test_phase3.py -q`.

When using the locked environment, the equivalent is:

```powershell
uv run --locked --no-sync python -m pytest
```

Use `--no-sync` only after `uv sync --locked` has provisioned the environment;
this prevents a verification command from unexpectedly accessing PyPI. When
package-index access is unavailable, do not add an ad hoc `--with pytest`
dependency: use the wrapper with the already-provisioned environment instead.

### Linked worktrees

Each linked worktree has its own ignored `.venv`, so `uv run --no-sync` is not
valid in a fresh worktree until `uv sync --locked --extra test` has provisioned
it. To run tests without creating another environment or accessing a package
index, point the wrapper at a compatible, already-provisioned project venv:

```powershell
$env:CCXT_PROJECT_VENV = 'C:\path\to\primary-worktree\.venv'
.\scripts\run-tests.ps1 tests/test_phase2.py -q
```

If a workflow specifically requires `uv run --no-sync`, point uv at the same
environment explicitly:

```powershell
$env:UV_PROJECT_ENVIRONMENT = 'C:\path\to\primary-worktree\.venv'
uv run --locked --no-sync python -m pytest tests/test_phase2.py -q
```

On POSIX shells, use:

```bash
CCXT_PROJECT_VENV=/path/to/primary-worktree/.venv ./scripts/run-tests tests/test_phase2.py -q
```

For `uv run --no-sync` on POSIX, use
`UV_PROJECT_ENVIRONMENT=/path/to/primary-worktree/.venv uv run --locked --no-sync python -m pytest`.

The shared environment is for read-only verification only. Provision the
linked worktree itself before commands that may synchronize dependencies.

### Mutation testing on Windows

Mutmut 3.x requires POSIX `fork`, so run a complete mutation campaign from a
WSL 2 Linux distribution rather than native Windows. The supported local
mutation runner uses Ubuntu:

```powershell
wsl --install -d Ubuntu
```

For a storage-constrained mutation runner, place this in
`%UserProfile%\.wslconfig` and run `wsl --shutdown` before starting the
distribution:

```ini
[wsl2]
memory=4GB
processors=2
swap=0
```

Run from the existing mounted working tree rather than cloning the repository
into the distribution:

```bash
cd "/mnt/c/TEST repos/ccxt-crypto-pipeline"
```

Mutmut's generated `mutants/` directory can be large. Preserve the campaign
evidence required by the active plan before removing it; never delete it only
to make a mutation result appear clean.

For Python changes, also run the relevant focused tests first and, when the
scope warrants it:

```powershell
uv run python -m compileall -q analysis ingestion normalization scheduler storage
git diff --check
```

Tests must use deterministic fixtures and mocks. Do not make live provider
calls from unit or fixture tests. Analysis/reporting acceptance paths must run
with network access disabled where the phase contract requires it.

The test suite should prove the behavior affected by the change, not merely
exercise implementation lines. Depending on scope, include:

- replay equality and stable normalized ordering;
- future-timestamp/look-ahead rejection;
- next-bar execution, fee/slippage, cash, and position-limit arithmetic;
- duplicate, missing, halted, insufficient-bar, and unavailable-data policies;
- address-scoped EVM/Solana identity joins and late-lineage exclusion;
- label censoring, sealed evaluation splits, baseline comparisons, uncertainty,
  and cost sensitivity;
- claim provenance, missing chart values, accessibility metadata, secret
  scanning, and package checks for reporting changes.

If a required check cannot run, report it as unverified with the concrete cause.
Do not weaken tests, coverage, validation, or security checks to make a change
pass.

## Storage and schema changes

DuckDB and Parquet are the canonical persistence boundary. If a change adds or
modifies a table, column, key, event/risk-flag type, partition, or persisted
record:

1. Read the storage migration procedure in
   [`.agents/skills/storage-schema-migration/SKILL.md`](.agents/skills/storage-schema-migration/SKILL.md).
2. Update the authoritative schema/accessor code in `storage/schema.py` and
   `storage/db.py` as applicable.
3. Bump `SCHEMA_VERSION` and provide an idempotent migration when existing data
   can be encountered.
4. Add fixture tests for fresh initialization, upgrade, repeat application,
   keys, nullability, and rollback/error behavior.
5. Document the migration and verify that raw ingestion rows retain their
   meaning.

Do not create a second database or rewrite raw rows to avoid storage review.
File-based analysis/reporting artifacts are acceptable only where the active
phase contract permits them.

## Provider and ingestion changes

Provider work must remain behind the existing normalized interfaces and routing
contracts. Before changing a version-sensitive provider integration:

- verify current behavior from authoritative provider documentation;
- preserve authentication, pagination, rate-limit, retry, timestamp, and unit
  semantics;
- distinguish unsupported, unavailable, transient, and authenticated failures;
- normalize addresses and event meanings without collapsing chain identities;
- never log, hardcode, or persist credentials;
- use deterministic fixtures for success, partial/malformed, retry, and
  unsupported-capability cases.

Do not add a paid fallback or substitute a semantically different provider just
to make a test or job appear successful.

## Pull requests

A pull request should be narrow enough to review as one behavioral change. Its
description must include:

- the problem and intended behavior;
- the active phase and files/boundaries affected;
- architectural or storage-contract impact;
- tests and exact verification commands with outcomes;
- offline/replay evidence when relevant;
- migration, configuration, security, or documentation impact;
- unresolved limitations or explicitly unverified checks.

Reviewers should be able to reproduce the result from the PR, the checked-in
fixtures, and the documented commands. Numeric research or reporting claims
must remain traceable to approved local evidence and must not be presented as
profitability, predictive alpha, or production readiness without the required
methodology and review.

Prefer squash merging when intermediate commits describe process rather than
durable semantic boundaries. Preserve separate commits only when their
boundaries materially help review, rollback, migration sequencing, or
bisecting. Do not rewrite published history or force-push without explicit
authorization.

## Documentation and security

Update documentation when commands, configuration, schema, phase status,
provider capability, or user-visible behavior changes. Documentation must
describe implemented behavior, not an aspirational future design.

`python -m pytest tests/test_documentation_consistency.py` checks selected
public facts against `storage/schema.py`, `pyproject.toml`, and the status
headings in `ROADMAP.md`. It covers schema version, minimum Python version, and
high-visibility phase state; subjective documentation consistency still
requires review.

If you discover an exposed credential or secret, stop using it, revoke or
rotate it, remove it from all affected artifacts, and notify the maintainers
privately through GitHub. Do not publish the value in an issue, pull request,
log, test fixture, report, chart, or commit message.

The repository currently has no `LICENSE` or `CODE_OF_CONDUCT.md`. Until those
policies are added, do not assume that the code is broadly reusable or that a
separate conduct-enforcement process exists. See [`SECURITY.md`](SECURITY.md)
for vulnerability reporting and secret-handling rules. For usage questions and
non-sensitive issue discussion, see [`SUPPORT.md`](SUPPORT.md).
