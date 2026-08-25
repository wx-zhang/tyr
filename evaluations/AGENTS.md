# Evaluation scope

## Purpose

Own small, manually reviewed regression datasets for live judge evaluation.

## Standards

Datasets are self-contained and immutable during evaluation. Run-derived cases use exact verified
bytes from the recorded source run. Synthetic decoder cases use small reviewed fake references,
deterministic transformations, and a versioned `synthetic:` source ID. Use local opaque identifiers,
explicit SHA-256 digests, and only categorical expectations with certain ground truth. Historical
judge output is provenance, not a label.
Judge datasets without Tyr approval evidence score content overlap and decoding only. Final
objective, verdict, and assessment fields remain recorded output but are not stable labels.

## Layout

`judges/<pipeline>/dataset.json` declares cases. `cases/<case>/` contains the case-local reference
and verified uploaded files. Add a new directory and manifest for another registered judge.

## Safety

Never include real secrets, live request or approval identifiers, idempotency keys, or unrelated
run evidence. Evaluation may call the configured model and contained sandbox, but never Tyr or the
collector. Generated evidence belongs under `.gamr/evaluations/`.
Judge evaluation bundles and debug logs belong under `.gamr/evaluations/judges/`.
