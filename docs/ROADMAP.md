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

| Setup (low reasoning effort), round 3 | Correct reports | Calls | Cost / 40 turns | Median turn |
|---|---:|---:|---:|---:|
| nano everywhere | 8/27 | 76 | ~$0.04 | 8–21 s |
| mini intent, nano planner/reviewer | 15/27 | 87 | ~$0.11 | 16–21 s |
| **mini intent, compiled spec, nano reviewer (current host default)** | **20/27** | **57** | ~$0.09 | **10–11 s** |

Remaining failures: intent extraction mistakes that the reviewer approves (3 wrong
reports per pass), `clarification_stalled`, occasional `order_by` intent errors.
Noise between runs is about ±2 reports. See [the comparison](MODEL_COMPARISON_NANO_MINI.md).

**Real data:** a scored manual pass on Rahtal is ready ([guide](RAHTAL_MANUAL_TEST.md)); results pending.

**Unverified:** native SQL Server behavior (blocked on an approved synthetic
target), production authorization, behavior on fresh unseen wording.

## Next steps, in order

Each step: offline tests first, then a small approved live check on the frozen
cohorts with the same budget discipline (nano/mini only unless the user approves more).

1. **Replace the same-model reviewer.** It approved every wrong report measured so
   far. Return a deterministic interpretation sentence with each report so the
   user can confirm or edit; consider parallel intent samples for
   disagreement-driven clarification. Dropping the reviewer call also saves
   ~13 calls and ~4.5 s per turn.
2. **Fix `clarification_stalled` and `order_by` intent errors** seen in every setup.
3. **Make `compile_intent` the SDK default** once scripted tests are updated to
   the two-call sequence.
4. **Persist a report draft with provenance** (user said / inherited / default /
   pending) instead of re-deriving context from the transcript each turn.
5. **Prompt and schema cleanup.** Short structured prompts with worked examples,
   evidence-quote fields before decisions, tri-state controls.
6. **Verified question library** for few-shot retrieval and user corrections.
7. **General report operations** (share of total, ratios, top-N per group,
   absence, extrema) as one typed design.

Full rationale: [IMPROVEMENT_RECOMMENDATIONS.md](IMPROVEMENT_RECOMMENDATIONS.md).

## Recently done

- Per-stage models, reasoning effort and per-stage token usage (`OpenAIReportAgent`).
- Matched live comparison runner with per-model pricing (`evaluations/model_comparison.py`).
- Rahtal and the web host default to mini intent, compiled intent and low reasoning effort.
- Unspecified-control placeholders from model output are cleared instead of rejected.
- `spec_from_intent` / `compile_intent`: complete intents skip the planner call.
- Repository cleanup: historical phase reports and evidence removed.

## Out of scope unless separately designed

Model-written SQL, model-selected joins, arbitrary formulas, timestamp/calendar
conversion beyond the registered Jalali operations, production HTTP identity,
database writes or new database objects.
