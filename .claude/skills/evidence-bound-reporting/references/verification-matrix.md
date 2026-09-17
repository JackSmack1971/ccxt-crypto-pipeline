# Reporting verification matrix

Use the narrowest applicable rows, plus every repository-required broader gate.

| Change class | Required focused evidence | Dangerous negative case | Broader evidence |
|---|---|---|---|
| Claim derivation/model | source/operation/unit/format round-trip | correct evidence pointer but wrong emitted value is rejected | package replay + full Phase 4 tests |
| Comparative claim | both sides/baseline and direction verified | reversed direction, missing baseline, incompatible units rejected | package replay |
| Chart transform | allowed transform executes deterministically and provenance records it | unknown/invalid transform rejected, not ignored | renderer/package replay |
| Annotation | declared annotation is deterministically rendered/represented | unimplemented annotation rejected | rendered SVG inspection |
| Missing-value policy | explicit unavailable state or configured failure | missing value does not become zero/disappear | package inspection |
| Handoff/input contract | approved immutable hash-verified input accepted | changed artifact/research hash, unknown field, incomplete approval rejected | cross-phase fixture if affected |
| Renderer/accessibility | units/source/role/title/description and relevant structure verified | malformed/unsupported structure rejected | `reporting_guard.py --package ...` |
| Package identity/checksums | repeated generation is byte/normalized equivalent | same identity with differing bytes conflicts | guard + replay |
| Security/privacy | package contains no credential or unintended local path | seeded secret/path fails | guard + repository security tests |
| Offline boundary | generation succeeds with network denied | provider/network dependency fails test | full Phase 4 offline fixture |

## Completion evidence classification

- **PASS:** the required check ran and observed the expected behavior.
- **BLOCKED:** a required prerequisite is absent or a boundary conflict prevents safe execution.
- **UNVERIFIED:** use only where repository policy allows missing non-required/external evidence. Never relabel a required unavailable check as PASS.
- **FAIL:** the current slice demonstrably violates the acceptance condition.

## Independent package inspection

When an affected package can be generated:

1. inspect `review.json` and verify it remains pending/review-required;
2. verify package-manifest identity, immutability, validation state, input identities, and checksums;
3. recompute declared artifact hashes independently;
4. inspect claim/derivation ledger rather than only article prose;
5. inspect chart specs and rendered SVG together;
6. scan artifact bytes for secrets, secret-bearing URLs, and local paths;
7. compare a replayed package under the repository's determinism definition.

The bundled `reporting_guard.py` mechanically covers a subset of these checks. Its success is evidence, not a substitute for semantic tests.

## Pre-existing versus introduced failures

If a broader suite fails:

- establish whether the failure existed before this slice when practical;
- never call a failure pre-existing from intuition alone;
- never claim completion through a repository-required failing gate;
- report the smallest reproducible failure and whether it blocks the reporting acceptance contract.
