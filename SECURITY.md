# Security Policy

`ccxt-crypto-pipeline` is a local-first crypto data-ingestion and research
pipeline. It handles provider credentials, RPC URLs, externally supplied market
and on-chain data, local DuckDB/Parquet stores, and generated research/reporting
artifacts. Security reports are welcome when they identify a concrete risk in
the repository, its documented operation, or its generated outputs.

## Supported code

There are currently no published releases or supported maintenance branches.
Security fixes are developed against the latest commit on `main` and may be
backported only when a maintained branch is introduced.

The repository is research software. Passing tests does not make a strategy
profitable, a provider reliable, or a workflow suitable for production. No
phase authorizes wallet custody, live or paper trading, automated execution,
transaction signing, or external publication.

## Reporting a vulnerability

Please do not open a public issue, pull request, discussion, or commit that
contains an exploitable vulnerability, credential, secret-bearing URL, private
data, or a complete proof of compromise.

Preferred channel:

1. Use GitHub's private vulnerability reporting flow for this repository, if it
   is enabled: [Report a vulnerability privately](https://github.com/JackSmack1971/ccxt-crypto-pipeline/security/advisories/new).
2. If private reporting is unavailable, contact the repository owner privately
   through GitHub and request a confidential channel before sending details.

There is no dedicated security team or guaranteed response-time SLA at this
stage. Reports will be assessed privately, and the reporter will be contacted
when more information or coordinated disclosure is needed.

### Include

Provide enough information to reproduce and assess the issue without exposing
secrets or personal data:

- a concise description and affected security boundary;
- impact, attack prerequisites, and likely confidentiality, integrity, or
  availability consequences;
- affected commit, module, command, configuration path, or dependency version;
- minimal reproduction steps or a sanitized proof of concept;
- whether the issue requires provider credentials, network access, or local
  filesystem access;
- any known mitigation and whether the issue has already been exploited.

Redact API keys, bearer tokens, passwords, RPC credentials, wallet material,
secret-bearing URLs, private datasets, and identifying user information. Do not
attach a live database, Parquet dataset, provider response containing secrets,
or generated package that has not been inspected.

## Credential and secret exposure

If a credential or secret may have been exposed:

1. Stop using it and revoke or rotate it immediately through the provider.
2. Preserve only sanitized evidence needed to establish scope; do not copy the
   secret into another issue, log, fixture, artifact, or commit.
3. Notify the maintainers privately using the channel above.
4. Identify affected commits, branches, artifacts, logs, local stores, and
   provider accounts so the exposure can be contained.
5. Remove the value from the working tree and history only through an agreed
   remediation plan; deleting a file alone does not remove a committed secret.

The repository expects `.env` files, local DuckDB/Parquet data, and generated
local outputs to remain untracked. Configuration examples must contain empty or
clearly non-secret values. Secrets must not appear in manifests, reports, chart
data, article text, image metadata, error messages, or test output.

## Security boundaries and design requirements

Contributors must preserve the following boundaries:

- External exchange, aggregator, explorer, RPC, and Solana API access belongs
  only in `ingestion/` adapters. Analysis and reporting must be offline-capable
  and consume local persisted inputs or approved local artifacts.
- Credentials and RPC URLs are read from the documented environment/config
  contract. Never hardcode, print, persist, or include them in exception text.
- Unsupported or unavailable provider capability remains explicit. Do not turn
  missing risk data into a safe value or silently substitute a paid or
  semantically different provider.
- DuckDB and Parquet are local persistence boundaries. Validate paths,
  identifiers, timestamps, and externally supplied payloads before persistence;
  preserve idempotency and schema-version rules.
- Analysis and reporting must not rewrite raw ingestion rows, use future data,
  collapse address-scoped identities by symbol, or leak later-discovered
  lineage into earlier decisions.
- Generated run, research, chart, and article artifacts must be deterministic,
  immutable where their contract requires it, provenance-rich, and free of
  unintended local paths or secrets.
- Phase 4 packages are review artifacts only. They must not publish externally,
  make automated trading decisions, or add unsupported factual claims.

## Safe testing and research conduct

Security testing must be authorized and proportionate to the local repository.
Use deterministic fixtures and mocks for unit and acceptance tests. Do not:

- probe or abuse exchanges, RPC endpoints, explorers, aggregators, or other
  third-party infrastructure;
- bypass provider authentication, rate limits, access controls, or paid tiers;
- submit transactions, sign messages, access wallets, or test live execution;
- intentionally exfiltrate local credentials, private datasets, or user data;
- add a live network dependency to offline analysis/reporting tests; or
- include a real secret or complete secret-bearing URL in a reproduction.

Provider outages, rate limits, stale observations, malformed upstream data, and
unsupported capabilities should be reported as reliability/data-quality issues
unless they create a separate security impact such as credential disclosure,
request forgery, unauthorized access, or integrity compromise.

## Dependency and provider risk

Dependency or provider changes require review of current authoritative contracts,
authentication, request construction, response parsing, retry behavior, limits,
units, timestamps, and capability differences. Pin or update dependencies only
through the project manifest and lockfile. Do not add a dependency solely to
avoid a validation or security boundary.

Security-sensitive changes should include deterministic tests for malformed and
partial responses, error redaction, unsupported capabilities, path or identity
validation, and offline behavior where applicable. Storage changes must follow
the migration and schema-version process in
[`.agents/skills/storage-schema-migration/SKILL.md`](.agents/skills/storage-schema-migration/SKILL.md).

## Disclosure and remediation

Maintainers will classify a report, reproduce it where safe, contain active
exposure, and coordinate a fix or mitigation privately. A public advisory or
release note may be issued after a fix is available and affected credentials or
data have been contained. The timing and content of disclosure will depend on
exploitability, provider coordination, and the risk of enabling further abuse.

This policy does not grant permission to access systems outside the repository.
Testing that affects external providers, accounts, infrastructure, or personal
data requires explicit authorization from the owner of that system.
