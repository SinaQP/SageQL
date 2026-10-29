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

| Setup (low reasoning effort) | Correct reports | Cost / 40 turns |
|---|---:|---:|
| nano everywhere | 6/27 | ~$0.03 |
| **mini intent, nano planner/reviewer (current default)** | **17/27** | ~$0.11 |

12 of nano's failures were one `comparison_specified` format inconsistency. Mini's
remaining failures include planner/intent disagreement and clarification stalls.
See [the comparison](MODEL_COMPARISON_NANO_MINI.md).

**Unverified:** native SQL Server behavior (blocked on an approved synthetic
target), production authorization, behavior on fresh unseen wording.

## Next steps, in order

Each step: offline tests first, then a small approved live check on the frozen
cohorts with the same budget discipline (nano/mini only unless the user approves more).

1. **Normalize intent format errors.** Treat an unspecified comparison as null
   (and similar paired flags) during intent normalization so a format slip is not
   a rejection. Re-test nano to see how much of the gap closes.
2. **P0-2: compile the spec from intent.** Build `ReportSpec` deterministically
   from the checked intent and skip the planner call when it is complete. Removes
   one model call and the planner/intent disagreement failures.
3. **Replace the same-model reviewer.** Return a deterministic interpretation
   sentence with each report so the user can confirm or edit; consider parallel
   intent samples for disagreement-driven clarification.
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
- Rahtal and the web host default to mini intent with low reasoning effort.
- Repository cleanup: historical phase reports and evidence removed.

## Out of scope unless separately designed

Model-written SQL, model-selected joins, arbitrary formulas, timestamp/calendar
conversion beyond the registered Jalali operations, production HTTP identity,
database writes or new database objects.
