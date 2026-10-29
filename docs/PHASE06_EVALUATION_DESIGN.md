# Phase 06 evaluation contract

2026-10-26. Written before Phase 06 implementation. Offline engineering is
authorized; external model execution is not authorized by this assignment.

## Scope and integration

Extend the existing trajectory runner, independent reference arithmetic, scorer,
real public SDK, persistent SQLite sessions and read-only recording adapter.
Keep earlier corpora, freezes and measured records immutable. New fresh questions
have separate assessment, development and transport-protocol cohorts. Scripted
and mocked protocol results are never called model accuracy. No new analytics,
orchestration topology, model assignment or dependency is planned.

The standalone `python -m evaluations.phase06` command defaults to offline.
Protocol mode injects responses into the real supported transport. Live mode
requires a matching reviewed approval file and explicit command opt-in; it uses
the SDK's existing configured Chat Completions adapter, never fallback scripts.
Only synthetic registrations/data are used. Answers and reference rows stay local.

## Independent outcomes and diagnostics

Freeze authored questions, complete typed specifications, exclusions, independent
rows/types/order/presentation and required clarification/denial/unsupported/block
outcomes before first execution. Score every turn through the existing scorer;
do not change denominators to count safety blocks as reports. Record exposure.
Use local allowlisted booleans/reason codes/stage names/counts/timings/hashes;
never persist raw transport payloads, exception text, private rows or inventories.
Reference diagnostics must themselves survive malformed/unissued responses.

## Approval and budgeting

Bind approval to exact corpus/freeze, selected case order, source/evaluator,
provider adapter, endpoint, model and absolute output directory. Require explicit
human authorization, synthetic-only review, positive request/input/output/total
token, wall-time and USD ceilings, per-call output cap, reviewed dated prices
and reviewed provider accounting/output-limit assumptions. No credentials belong
in approval or diagnostics. Load a key only after validation; never load `.env`.

Reserve full serialized request bytes (including structured schema), reviewed
provider overhead and output cap before dispatch; charge worst reviewed input/
output rates, without assuming cache discounts. This requires provider-specific
operator verification of the estimator and billing categories; otherwise live
preflight refuses. Actual usage may reduce reservations only with complete valid
input/output accounting. Cached-input/reasoning details are informational subsets,
not double-counted. Missing/inconsistent usage retains reservations; unexpected
usage beyond bounds stops dispatch. This is conservative local accounting, not
a certified provider invoice or universal tokenizer/billing cap.

Persist every reservation before dispatch and every safe result afterwards.
Failed/uncertain calls retain their reservation. Timeouts share remaining run
time; retries and endpoint/model switching are forbidden. Sequential dispatch
only. Budget exhaustion records unexecuted turns/cases rather than successes.

## Interruption and resumption

Use an exclusive local run lock plus atomic durable JSON checkpoints. Preserve
first results. Resume must match immutable configuration and hashes, retain all
usage/reservations and elapsed wall time, and skip completed trajectories.
An interrupted trajectory retains completed turn measurements and is finalized
as interrupted; uncertain calls/turns are never automatically repeated. Continue
only untouched trajectories. A new deliberate experiment needs a new directory
and separate approval. SDK session formats remain unchanged.

## Protocol investigation and change policy

Test issued, fabricated, altered, wrong-owner, stale and hidden references,
canonical scalars, display text, malformed/extra-field JSON and SQL-bearing
responses. Distinguish protocol validity from semantic correctness. Verify local
payload isolation at intent, planning, review and refinement. A production change
requires a focused failing reproduction and bounded correction, with preserved
before evidence and unchanged expected outcomes. No prompt/topology optimization
without real supporting evidence. Phase 07 does not start automatically.
