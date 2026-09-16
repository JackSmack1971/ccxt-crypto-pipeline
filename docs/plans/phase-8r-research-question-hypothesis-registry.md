# Phase 8R.3 — Research question and hypothesis registry

The registry is the durable declaration boundary above an experiment spec. A
question describes the intended inquiry; a hypothesis describes one testable
claim linked to that question; an experiment spec declares the executable
methodology; and a run records the result. None of these declarations may be
inferred from a result after the fact.

`ResearchQuestion` and `ResearchHypothesis` are versioned, validated, and
content-identified. Required declarations include the universe, treatment,
features, outcomes, temporal availability, confounders, baseline, minimum
effect, statistical/validation policies, falsification policy, failure
interpretation, applicable dataset identities, and provenance.

`ResearchRegistry.bind_experiment` checks the hypothesis link and feature and
outcome compatibility, then returns an experiment spec whose content identity
includes both registry IDs. Experiment manifests repeat those IDs. Registry
JSON is immutable and replayable under its content-derived identity.

This contract is local and offline. It does not claim that a declaration is
scientifically correct, that a dataset is fit for every question, or that a
result supports execution.
