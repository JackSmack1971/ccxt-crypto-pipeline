# Phase 8 publication closure matrix

This matrix closes Slice 8.6. It proves the local publication-preparation
boundary over an immutable approved research handoff. It does not authorize
external publication or live-provider behavior.

| Criterion | Evidence | Status |
| --- | --- | --- |
| Source-to-claim traceability | `tests/test_phase8_closure.py::test_phase8_publication_closure` generates a package from the canonical approved handoff, verifies the claim ledger's evidence pointer and typed derivation, and checks the package's linked research identity and staged-input hashes. | PASS |
| Deterministic renderer replay | The closure test generates the package twice and compares every package artifact byte-for-byte, including article, HTML, chart, ledger, and manifest outputs. | PASS |
| Accessibility | The closure test runs the repository SVG accessibility validator against the emitted chart and confirms the HTML retains pending review state and inline chart output. | PASS |
| Review history and supersession | The closure test records an initial approval and a later approval that supersedes it, then verifies the export contains only the effective approval and retains its reviewer identity. | PASS |
| Export traceability and immutable checksums | The closure test verifies the exported manifest's source package identity and independently recomputes every exported file hash; repeated export returns the same immutable directory. | PASS |
| Secret and local-path hygiene | The closure test scans all exported bytes for credential markers and absolute local paths; `tests/test_phase8.py` separately proves seeded secret content is rejected. | PASS |
| Offline boundary and review gate | The closure test denies socket creation during generation and export, and confirms generated package review remains `pending` with `approval_required`. | PASS |

External posting, distribution, and any live-provider acceptance remain outside
the Phase 8 contract and are intentionally unverified.
