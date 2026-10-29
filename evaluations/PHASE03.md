# Phase 03 trajectory evaluation

This guide records the historical Phase 03 experiment. See [Phase 04](PHASE04.md)
for current outcomes: P02 now completes correctly, D03 clarifies before reads and
D02 remains blocked. Original frozen expectations and historical results below
are retained. The stage-aware fault driver can now respond to local ordering
rejection as well as grouping rejection; comparable before/after runs use that
same driver against preserved starting sources and current sources.

**Offline evaluation complete; live-model generalization unverified.**
Scripted responses deliberately supply selections or faults. Their pass rate
measures enforcement, execution and scoring, not interpretation of unseen text.

## Suites and reproducibility

Run from the checkout with the existing development environment:

```powershell
.\.venv\Scripts\python.exe -m evaluations --strict
.\.venv\Scripts\python.exe -m evaluations --suite holdout --strict
.\.venv\Scripts\python.exe -m evaluations --suite development
.\.venv\Scripts\python.exe -m evaluations --suite pipeline
.\.venv\Scripts\python.exe -m evaluations --suite phase03
.\.venv\Scripts\python.exe -m evaluations --suite development --case D04
.\.venv\Scripts\python.exe -m pytest tests/test_phase03_evaluations.py -q
```

The default `regression` suite preserves the original 61 cases and its CLI/cohort
behavior. `--suite holdout|development|pipeline|phase03` selects the new versioned
trajectories using the same SDK, adapters, transport decoding and outcome scorer.
New suite defaults write ignored `dist/phase03/<suite>.json`; use `--output` for
a separate measured record. There are no known-failure waivers in these suites.
Exit 1 means at least one requested outcome was not fulfilled, even when an
uncooperative provider was safely blocked. Exit 2 is a configuration/input error.

Current expected measured exits: fixed regressions 0; holdout 0; development,
pipeline and combined Phase 03 **1**. The latter retain a safely blocked custom
provider and two accepted wrong reports. They are not passing report completions.
See `docs/PHASE03_ENGINEERING.md` for findings and justification for scoped follow-up.

## Provenance, freeze and exposure

`phase03/records.json` contains authored workshop source rows, including another
organization, a voided job and exclusive-endpoint traps. `phase03_hosts.py`
registers that host using existing operations and reuses the two existing hosts
only for trusted registrations/seed data. `reference.py` contains no SageQL
imports, SQL or returned-result oracle. It calculates groups, aggregates, filters,
periods and ordering independently in Python. Its retail/library facts are
independent normalized source statements, not the example's expected rows.

Every turn declares its request, expected classification, complete target spec,
material field requirements, exclusions and exact reference results when relevant.
Actor/initial-state descriptions are explicit; controls declare revocation,
restart and synthetic stage faults. Public spec fields are checked independently
from reviewer approval. Reference data/answer keys are never model-visible inputs.

The initial 40 trajectories were frozen in `cases.v1.json`/`freeze.v1.json` before
agent execution. First results remain in `baselines/phase03_initial_v1.json`.
Independent review found an oracle error: a policy-filtered library dimension
uses a registered LEFT JOIN, retaining a visible fact with NULL Shelf. It also
corrected reference grouping tie order and a static response queue that supplied
a plan to the reviewer. These changes are explained in
`phase03/history/corrections.v2.json`; initial corpus/record/oracle remain available.

H12 and H25 were exposed and used for targeted fixes. They are **development**
cases in v2; H31/H32 replace them with independently authored holdouts.
`cases.v2.json` and `freeze.v2.json` were frozen before running that revision.
Final composition: **30 holdout, six development, six pipeline trajectories**.
The 30 include 28 previously exposed assessment cases and two replacements.
They are not a permanently secret or untouched blind benchmark. None of the final
holdouts was used to target a production fix. Repeated scripted verification
does not establish language generalization.

Hash validation rejects changed frozen assets. For a genuine reference correction,
retain the old version, document independent justification, create a new version
and freeze it before execution. Promote any assessment used to engineer a targeted
fix, record the exposure and author a fresh replacement. Do not change expected
outcomes after observing a failure to improve a score.

Phase 01/02 archives and their original hashes are preserved. `baseline.json`
remains the historical Phase 02 record; current fixed-regression measurements are
in `baselines/phase03_regression.json`. New comparable before/after and separate
cohort records use the `phase03_*.json` names. Full local generation artifacts
remain ignored under `dist/phase03/`.

## Scoring, instrumentation and limitations

Each submission is scored, including earlier turns in a conversation. A trajectory
is correct only if every planned turn executes and is correct. The first failing
turn is retained; later success cannot erase it. Requirements compare the complete
accepted public specification, exact rows/columns/types/order, bounds, presentation
and truncation. Required-report turns without a returned report get no requirement
credit. Replay, persisted reports, previous-success preservation, source bytes,
no-read outcomes and model-payload isolation are checked on real SDK paths.

Supported completion is correct reports / submitted turns requiring reports.
Semantic correctness uses returned reports as denominator. Requirement completeness
is satisfied field checks / all 13 field requirements per supported turn; it is
not a substitute for complete-report correctness. Trajectory correctness has a
separate trajectory denominator. Clarification, unsupported and denial fractions
remain separate; empty populations have null rates. Injected operational faults
never count as completed reports. A safe block of an intentionally wrong custom
provider remains an unfulfilled supported request.

Allowlisted stage diagnostics compare decoded/effective intent, proposals and
review decisions with independent requirements. They distinguish extraction,
context, planning/review disagreement, deterministic mismatch, incorrect accepted
specification/data, incomplete results, unnecessary clarification, unsupported
classification, authorization and transport/database failures. Reviewer counters
classify the proposal independently; a legitimate proposal followed by an injected
database failure is still a correct reviewer approval. Controlled useful and
unproductive revisions are reported separately; this is not a measured live
reviewer error rate or evidence for changing model assignments/topology.

Transport calls and milliseconds are recorded by intent/planning/review stage,
along with actual revisions/repair/reconsideration and adapter calls. Local
scenario time excludes fixture construction and verification/cache probes. Tokens
are null when response usage is absent; coverage is explicit. Offline cost is
undefined. Calls with a transport exception count once. No raw provider exception,
prompt, row values, SQL, filter/policy values, identity or credentials enter the
measurement artifacts. Public requirement names and boolean checks may appear.

Coverage includes English, Persian, mixed terminology, exact labels/aliases,
multi-metric/filter/ranking/date requests, quotes, exclusions, unavailable concepts,
ambiguity, comparisons, injection, tenant boundaries, revocation, clarification,
several refinements, earlier reports, reopen and replay. Gaps include additional
languages, longer discourse, broad paraphrase distributions, live extraction,
real SQL Server behavior, implicit constraint persistence and snapshot consistency.

## Exact opt-in live procedure (not executed)

Live evaluation transmits synthetic questions and permitted business metadata and
may incur charges. Existing configuration is not authorization. This phase has no
such authorization and makes no external model calls.

After explicit authorization for this evaluation:

1. Review the synthetic cases, endpoint and model. Configure only
   `SAGEQL_EVAL_API_KEY`, `SAGEQL_EVAL_BASE_URL`, `SAGEQL_EVAL_MODEL` through the
   host's secret mechanism. The runner never loads `.env` or Rahtal configuration.
2. Copy `phase03/live-approval.example.json` to an ignored local path. Its defaults
   intentionally prohibit execution. Record the exact reviewed endpoint/model,
   explicit approval, request/token/time/USD ceilings and current operator-verified
   pricing with source URL and verification timestamp. No secret belongs in this
   file. The runner validates the approval; it does not independently fetch prices.
3. Select a small reviewed set and a **new output path**:

```powershell
.\.venv\Scripts\python.exe -m evaluations --suite holdout --case H01 --live --live-approval dist/phase03/live-approval.json --output dist/phase03/live-first-H01.json
```

Live runs use the configured client only: no scripted fallback or endpoint/model
switch, zero transport retries, one SDK-bounded planning revision, and only local
synthetic SQLite. H20/H27 host fault controls are excluded and listed explicitly;
development/pipeline suites cannot run live. Never point this evaluation at a
production database. Required budgets are shared across all stages/turns/cases.

Before dispatch, the runner reserves serialized UTF-8 prompt bytes plus the output
token cap, and estimates USD using the reviewed prices. Reported usage adjusts
the reservation afterwards; absent usage keeps the conservative reservation.
The next call cannot exceed remaining accounted request/token/time/USD limits;
dispatch timeouts are bounded by remaining time. Provider tokenization/billing
cannot be certified by this local estimator. Review provider limits/pricing and
keep the request/output caps small. This is a cost estimate, not an invoice.

Results checkpoint after each trajectory, including failures. Existing live
output paths are rejected to preserve first-attempt records. Budget exhaustion
stops the run; unexecuted trajectories/turns are explicit and are not represented
as completed requests. Persisted failed receipts are never automatically rerun.
Token/cost coverage and endpoint hash/model are recorded without API keys.

The live path is locally tested using an injected unavailable client and synthetic
usage/pricing. Those mocks are unit tests, not live measurements or real prices.
