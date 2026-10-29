# Nano vs mini stage comparison (2026-10-29)

First live use of per-stage models (recommendation P0-1). The question: which
step does `gpt-5-nano` fail on, and what does replacing only that step cost?

## Round 5: aborted by provider rate limits

Planned: setup D against setup E (D + 3 parallel intent samples). AvalAI answered
almost every call with HTTP 429 from the start, in both setups, so **no result
was obtained and intent sampling remains unmeasured**. A 429 on every call from
the first request suggests exhausted account credit/quota rather than burst load.

The runner kept reserving calls through the 429s because comparison runs continue
past failed turns. Reserved-but-unsettled estimates total $1.49; rejected requests
normally have no billed usage, but billing is unverified. Under the conservative
estimate the approved $2 is used up, so live tests stopped. The runner now halts a
batch on the first HTTP 429. Hosts keep setup D.

## Round 4: reviewer on vs off

Current source (adds the ordering-without-measure fix and report interpretation).
Both setups use mini intent, compiled intent and low effort; D drops the reviewer
(`review=False`).

| Setup | Correct reports | Complete trajectories | Wrong accepted | Model calls | Cost | Median turn |
|---|---:|---:|---:|---:|---:|---:|
| C: with nano reviewer | 22/27 | 13/18 | 3 | 62 | $0.073 | ~10.8 s |
| **D: no reviewer** | **22/27** | **13/18** | **2** | **34** | $0.088* | **~6.8 s** |

\* D's cost includes the full reservation kept for one dropped mini call; its
settled calls cost less than C's.

- **The reviewer adds nothing measurable**: same correct reports, no fewer wrong
  ones, almost twice the calls and ~4 s more per turn. Hosts now use D, and each
  report shows its interpretation (filters, conditions, sort, limit) so the user
  can catch the remaining intent mistakes.
- Remaining wrong reports are intent extraction errors: a lost filter (N02.4),
  a wrong period (N04.2, every round), a wrong limit (N01.3) and a missing change
  calculation (A07.1).
- C rose from 20 to 22 since round 3: N06 now asks for the measure (ordering fix),
  plus noise.

Round 4 spend: $0.161. **Running total about $0.61** of the approved $2.

## Round 3: after the placeholder fix and compiled intent

Same cohorts and runner, two SDK changes: unspecified-control placeholders are
cleared (commit `b5cd954`), and setup C compiles complete intents locally so the
planner call is skipped (`compile_intent=True`, commit `62fbb26`).

| Setup | Correct reports | Complete trajectories | Wrong accepted | Model calls | Cost | Median turn |
|---|---:|---:|---:|---:|---:|---:|
| A: nano everywhere | 8/27 | 7/18 | 5 | 76 | $0.042 | 8–21 s |
| B: mini intent | 15/27 | 9/18 | 3 | 87 | $0.107 | 16–21 s |
| **C: mini intent + compiled intent** | **20/27** | **12/18** | 3 | **57** | $0.094 | **10–11 s** |

- **C is best on every axis except wrong reports**, which equal B: more correct
  reports, a third fewer calls, cheaper and about twice as fast. Hosts now use C.
- C's three wrong reports are all intent extraction mistakes (a limit, a filter, a
  period); the period error also occurs in B. The reviewer approved all of them,
  again confirming it rarely catches real errors (roadmap step 3).
- The placeholder fix helped nano only a little (6 → 8). With its format errors
  removed, nano reached the planner more often but produced five wrong accepted
  reports (mostly wrong time grain or grouping). Nano is not reliable for intent.
- B moved from 17 to 15 between rounds with no relevant change: run-to-run noise
  is about ±2 reports at this sample size.
- Remaining failures: `clarification_stalled` (all setups), occasional
  `order_by` intent constraint errors, dropped provider connections (2–4 per round).

Round 3 spend: $0.243 estimated. **Running total about $0.45** of the approved $2.
Raw journals and `analysis.json` are in ignored `dist/comparison/r3/`.

## Round 2 (first measurement)

## Setup

| | Setup A | Setup B |
|---|---|---|
| Intent | gpt-5-nano | **gpt-5-mini** |
| Planner / Reviewer | gpt-5-nano | gpt-5-nano |
| Reasoning effort | low (all stages) | low (all stages) |

- Same frozen synthetic SQLite cases for both: Phase 14 `independent` (N01–N06,
  19 turns, 13 report goals) and `legacy` (A01–A12, 21 turns, 14 report goals).
- AvalAI `https://api.avalai.ir/v1`, Chat Completions. Published rates observed
  2026-10-29: nano $0.05 / $0.40, mini $0.25 / $2.00 per million input/output tokens.
- Runner: `python -m evaluations.model_comparison` (shared Phase 06 runner, budget,
  journal and scorer). SDK source fixed at commit `f2d91de` for every run.
- Approved by the user in chat on 2026-10-29: nano and mini only, about $2 total.
- Differences from the Phase 14 assessment procedure: wrong synthetic reports are
  scored without stopping the batch, and a dropped provider connection fails only
  its turn (no retry; its reservation stays in the budget). Isolation failures
  and denied reads still stop a run. One sample per turn.

## Results

| | A independent | B independent | A legacy | B legacy | **A total** | **B total** |
|---|---:|---:|---:|---:|---:|---:|
| Correct reports | 4/13 | 6/13 | 2/14 | 11/14 | **6/27 (22%)** | **17/27 (63%)** |
| Complete trajectories | 2/6 | 1/6 | 4/12 | 9/12 | 6/18 | 10/18 |
| Wrong accepted reports | 0 | 1 | 2 | 0 | 2 | 1 |
| Turns lost to dropped connection | 1 | 2 | 1 | 0 | 2 | 2 |
| Model calls | 20 | 39 | 28 | 47 | 48 | 86 |
| Estimated cost (USD) | 0.0133 | 0.0640 | 0.0168 | 0.0458 | **0.030** | **0.110** |
| Cost per correct report | | | | | $0.0050 | $0.0065 |
| Median turn time | 7.6 s | 15.9 s | 10.0 s | 20.7 s | | |

Setup A turns look faster only because most of them fail at the first call. Median
latency per call was similar across setups: intent 7–9 s, planner about 6 s,
reviewer 4–7 s. That is much faster than the Phase 14 baseline (default effort,
about 18 s per intent call), so low reasoning effort is worth keeping.

### Where nano fails

Setup A's intent errors, from the turn diagnostics:

| Error | A independent | A legacy |
|---|---:|---:|
| `intent_constraints / comparison_specified` | 6 | 6 |
| `conditions` (invalid filter/threshold shape) | 0 | 2 |
| `intent_mismatch / repeated_conflict` | 0 | 1 |
| `clarification_stalled` | 2 | 1 |

**12 of nano's failures are the same structural error.** It returns a comparison
period while setting `comparison_specified=false`. `check_intent`
(`src/sageql/sdk/intent.py:249`) requires an unspecified comparison to be null, so
the whole intent is rejected before planning. This is a format inconsistency, not
a misunderstanding of the request. It is the schema problem described in
recommendation P1-6.

### Where mini still fails

Setup B's remaining errors: `intent_mismatch / repeated_conflict` (3, legacy),
`agent_exhausted` (2), `clarification_stalled` (2), one `order_by` constraint error,
and one wrong accepted report (N04 turn 2). The repeated conflicts are the
nano planner disagreeing with the mini intent, the failure class that
recommendation P0-2 (build the spec from intent without a planner call) removes.

### Cost

Mini on intent is 78% of setup B's cost ($0.086 of $0.110). Per correct report,
B costs about 30% more than A ($0.0065 vs $0.0050), but it produces almost three
times as many correct reports. A full 40-turn pass of setup B costs about $0.11.

## Conclusions

1. **Nano's planner and reviewer are not the main problem; its intent step is.**
   Replacing only intent with mini raised correct reports from 6/27 to 17/27.
2. **Most of nano's intent failures look cheaply fixable.** A deterministic fix
   for the `comparison_specified` inconsistency would remove 12 rejections. Two
   candidates: treat an unspecified comparison as null during normalization, or
   replace the flag pair with one tri-state field. Re-test nano after that fix
   before paying for mini permanently.
3. **P0-2 is the right next structural step.** The remaining B failures include
   planner/intent disagreement, which deleting the planner call removes.
4. **Keep low reasoning effort.** It roughly halved per-call latency versus Phase 14.

## Limits

- One sample per turn and 27 report goals per setup: differences of one or two
  reports are noise. The A/B gap (6 vs 17) is large enough to matter.
- Dropped connections cost B two independent turns, and later turns in those
  trajectories may have been affected.
- N and A cases now have additional live exposure. Fixes tuned on them need
  fresh held-out wording before any generalization claim.
- Costs are published-rate estimates; billed amounts are unverified. Failed calls
  keep their full reservation in the estimate.

## Spend

Round 2 (these results): $0.140 estimated. A first attempt stopped early on dropped
connections and is preserved in `dist/comparison/attempt1/`: about $0.066 including
reservations for failed calls. **Total about $0.21** of the approved $2.

Raw journals, responses and `analysis.json` are in ignored `dist/comparison/r2/`.
