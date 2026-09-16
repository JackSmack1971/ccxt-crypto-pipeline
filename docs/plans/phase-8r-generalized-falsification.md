# Phase 8R.4 — Generalized falsification framework

`FalsificationPolicy` is the pre-result declaration boundary for tests that
could disconfirm a research hypothesis. The policy is serialized into the
content-addressed experiment specification, so changing the declared test set
changes experiment identity.

Each declared method produces exactly one explicit result with `passed`,
`failed`, or `unavailable` status. Existing deterministic negative-control and
stability evidence supplies the implemented methods; declared methods without a
repository implementation remain unavailable. The aggregate status requires
all declared methods to pass and cannot be improved by omitting a failed or
unavailable method after results are known.

The artifact is local, deterministic, and methodological evidence only. It
does not establish alpha, profitability, or execution readiness.
