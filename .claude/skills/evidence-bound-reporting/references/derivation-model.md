# Evidence derivation model

Load this reference when changing factual claims, numbers/comparisons, units, chart transformations, annotations, or formatting.

## Why an evidence pointer is insufficient

A claim can point to the correct artifact and row while still state the wrong number. Evidence-bound reporting therefore needs two independently checkable facts:

1. **provenance:** where the approved evidence came from;
2. **derivation:** how the emitted value was obtained from that evidence.

A validator that checks only provenance proves the claim is *related to* approved evidence, not that the claim's factual value is correct.

## Minimum derivation information

Use the repository's actual schema. If the active task is defining that schema, make these concepts explicit enough to validate mechanically:

- source artifact identity;
- source row/key selector and field(s);
- operation identity and parameters;
- source unit(s) and result unit;
- missing/unavailable behavior;
- comparison baseline/denominator when applicable;
- rounding/formatting rule that maps the validated value to emitted text;
- output value or normalized representation used by rendering;
- upstream uncertainty/coverage/censoring reference when material.

Do not require every concept to be a top-level field if the repository has a better typed structure. Require equivalent inspectability.

## Operation design

Do not permit arbitrary expressions by default. Prefer a small explicit operation vocabulary whose semantics can be independently tested.

For each authorized operation, tests should cover:

- valid input;
- boundary/zero-denominator behavior where applicable;
- missing/non-numeric input;
- unit compatibility;
- deterministic output;
- formatting/rounding at boundaries;
- rejection of unknown parameters/fields when the contract is strict.

Do not assume operations such as ratio, percentage change, aggregation, annualization, or significance conversion are presentation-only. If an operation would change research semantics rather than present an already-approved result, it belongs upstream and must not be introduced in Phase 4.

## Rendering rule

Preferred flow:

`approved evidence -> derivation validator/evaluator -> validated typed value -> formatter -> prose/chart renderer`

Avoid:

`approved evidence -> free-form prose string -> regex check after rendering`

Post-render checks can be useful as defense in depth, but the source of truth should remain typed validated data.

## Numeric claims

A robust mismatch test intentionally makes the textual/rendered value disagree with the source while leaving provenance pointers valid. Validation must reject it.

If values are formatted, compare at the correct layer:

- validate exact/typed numeric derivation first;
- apply explicit rounding/formatting;
- assert the emitted representation matches that formatted value.

Do not use a tolerance to hide an undeclared formatting policy.

## Comparative claims

A comparative statement must identify both sides or the exact approved comparison result. Terms such as "higher", "lower", "outperformed", or "increased" are factual operations even if no numeral appears.

Reject a comparison when:

- baseline identity is absent/ambiguous;
- units are incompatible;
- source period/cohort differs without declared semantics;
- one side is unavailable;
- direction in emitted text disagrees with the computed comparison.

## Chart transformations

A chart transform is executable semantics, not decorative metadata.

- whitelist only operations the reporting contract explicitly supports;
- apply in declared order when order matters;
- persist enough information to replay the transform;
- reject unknown transforms and invalid parameters;
- never silently ignore a transform;
- never convert missing values to zero or drop them unless explicitly authorized.

If the transform computes a new research metric instead of a presentation representation, move it upstream.

## Annotations

Treat annotations as claims attached to a chart. They must either:

- derive from approved evidence/validated chart state under a declared rule; or
- be clearly non-factual presentation labels authorized by the spec.

Declared annotations that the renderer does not implement must fail validation. Silent omission produces a package that does not match its own specification.
