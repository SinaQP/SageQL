# SageQL roadmap

Phase-by-phase history (Phases 01–14) was removed on 2026-10-29 to keep this file
actionable; it remains in git history before commit `4dcd5b2`.

## Goal

A manager asks for a report in chat (Persian or English) and reliably gets the
correct, authorized report from host-registered data, quickly and cheaply. Models
interpret requests; deterministic code authorizes, compiles and executes.

## Where we are (2026-10-29)

**Solid:** registered catalog and policies, deterministic SQL Server/SQLite
compilation, read-only bounded execution, relationships, entity lookups and
labels, Jalali periods, comparisons, sessions with revisions and idempotent
receipts, snapshot read consistency. About 2,440 offline tests pass.

**Bottleneck:** understanding requests. On the frozen synthetic cohorts:

| Setup (low reasoning effort) | Correct reports | Calls | Cost / 40 turns | Median turn |
|---|---:|---:|---:|---:|
| nano everywhere (round 3) | 8/27 | 76 | ~$0.04 | 8–21 s |
| mini intent, nano planner/reviewer (round 3) | 15/27 | 87 | ~$0.11 | 16–21 s |
| mini intent, compiled spec, nano reviewer (round 4) | 22/27 | 62 | ~$0.07 | ~11 s |
| **mini intent, compiled spec, no reviewer (round 4, host default)** | **22/27** | **34** | ~$0.07 | **~7 s** |

Remaining failures: intent extraction mistakes (2–3 wrong reports per pass: a lost
filter, a wrong period, a wrong limit), shown to the user through the report's
interpretation line. `clarification_stalled` only follows failed turns. Noise
between runs is about ±2 reports. See [the comparison](MODEL_COMPARISON_NANO_MINI.md).

**Live budget:** the approved $2 is used up under conservative estimates (about
$0.61 settled plus $1.49 reserved for rate-limited calls); new live runs need
new approval.

**Real data:** a scored manual pass on Rahtal is ready (private guide); results pending.

**Unverified:** native SQL Server behavior (blocked on an approved synthetic
target), production authorization, behavior on fresh unseen wording.

## Next steps, in order

Each step: offline tests first, then a small approved live check on the frozen
cohorts with the same budget discipline (nano/mini only unless the user approves more).

1. **Collect the Rahtal manual test results** (private guide) and
   turn every real failure into an offline regression.
2. **Reduce intent extraction errors** (lost filters, wrong periods/limits).
   `intent_samples` (parallel samples with an agreement vote) is implemented but
   unmeasured: round 5 hit provider rate limits. Measure it once AvalAI credit is
   confirmed and a new budget is approved; then try evidence-quote fields before
   decisions in the intent schema.
3. **Let users correct the interpretation** with quick edit actions (period,
   measure, grouping) instead of retyping.
4. **Make `compile_intent=True, review=False` the SDK default** once scripted tests
   are updated to the shorter call sequence.
4. **Persist a report draft with provenance** (user said / inherited / default /
   pending) instead of re-deriving context from the transcript each turn.
5. **Prompt and schema cleanup.** Short structured prompts with worked examples,
   evidence-quote fields before decisions, tri-state controls.
6. **Verified question library** for few-shot retrieval and user corrections.
7. **General report operations** (share of total, ratios, top-N per group,
   absence, extrema) as one typed design.

Full rationale: [IMPROVEMENT_RECOMMENDATIONS.md](IMPROVEMENT_RECOMMENDATIONS.md).

## Recently done

- Saved reports: save a finished report once, re-run it with zero model calls,
  with dynamic dates and optional overrides ([contract](SDK_SAVED_REPORTS.md)).

- Per-stage models, reasoning effort and per-stage token usage (`OpenAIReportAgent`).
- Matched live comparison runner with per-model pricing (`evaluations/model_comparison.py`).
- Rahtal and the web host default to mini intent, compiled intent and low reasoning effort.
- Unspecified-control placeholders from model output are cleared instead of rejected.
- `spec_from_intent` / `compile_intent`: complete intents skip the planner call.
- Reports carry a deterministic interpretation (filters, conditions, sort, limit);
  the reviewer is optional and hosts run without it.
- Ranking without a chosen measure asks instead of sorting by a default metric.
- Optional parallel intent samples (`intent_samples`, default 1) that also
  tolerate one failed sample; comparison runs halt on HTTP 429.
- Repository cleanup: historical phase reports and evidence removed.

## Out of scope unless separately designed

Model-written SQL, model-selected joins, arbitrary formulas, timestamp/calendar
conversion beyond the registered Jalali operations, production HTTP identity,
database writes or new database objects.
