# Phase 04 filter and ordering evaluation

Offline scripted evaluation only; live-model generalization remains unverified.

```powershell
.\.venv\Scripts\python.exe -m evaluations --suite phase04 --strict
.\.venv\Scripts\python.exe -m evaluations --suite phase04_development --strict
.\.venv\Scripts\python.exe -m evaluations --suite phase04_assessment --strict
.\.venv\Scripts\python.exe -m evaluations --suite phase03
.\.venv\Scripts\python.exe -m pytest tests/test_sdk_filter_order_grounding.py -q
```

Phase 04 has 26 trajectories/33 turns: 21 development trajectories and five
assessment trajectories. The latter are explicitly authored language contrasts,
not secret/unseen live-language tests. Inputs/complete expected specifications,
independently computed data/order, policies and source records were frozen before
the changed SDK was evaluated. Tests outside the corpus are development evidence.
No assessment expectations were revised after execution. F/O cases guide targeted
changes; A cases are reported separately. Previous phase corpus/baseline/freeze
bytes are retained.

`phase04/cases.v1.json` contains the versioned inputs. `freeze.v1.json` binds it to
the original source records, independent `reference.py` arithmetic, three host
registrations and source fixtures. `phase04.py` verifies hashes. The unchanged
trajectory scorer checks every report field, rows/types/order, period bounds,
presentation and truncation, plus durable session retrieval, prior-report
preservation, replay without reads, policy denials and source/payload isolation.
Unknown literal values can correctly yield empty/null aggregates; fixtures never
enumerate database values in the SDK's catalog.

The runner uses stage-aware synthetic faults. First planning attempts omit a
filter or reverse a direction; subsequent attempts repair only when retried.
Persistent faults never repair. Custom providers return incomplete ready specs.
The existing P01/P02 reviewer approves/rejects the first bad candidate only if it
actually reaches review. Local preemption is measured separately. This removes a
static response-queue artifact (a review JSON object being decoded as a revised
plan); it changes no request, expected result or scoring rule. The comparable
starting-source run uses this same driver and reproduces 39/42, two wrong accepted
specifications. The first unchanged-driver starting reproduction is also saved.

The new suites use `--output` to select an artifact path (defaults remain compatible
with the earlier CLI). No waivers are used; exit 1 means an unfulfilled expected
outcome. Old Phase 03 scoring still expects a report for D03 and therefore counts
its new clarification as one unnecessary clarification/incorrect rejection. That
classification is deliberately retained, even though the registration lacks a
unique independently grounded value owner. D02 and D03 are not completed reports.
F05 separately demonstrates clarification plus correct completion after the owner
is supplied; F09/O11 demonstrate provider-neutral blocks. F07/O10 test persistence,
filter/metric/date changes, order reversal/removal and earlier reports/receipts.

Artifacts in `baselines/phase04_*.json` retain separate original/comparable starting,
final historical-cohort and new-cohort measurements. Source hashes identify the
package actually imported, including the preserved starting source snapshot.
Corpus and evaluator hashes identify the scoring inputs. Field completeness for
filters and ordering is reported only for required-report turns; a missing report
gets zero credit. It must not be replaced by a rate over successful reports alone.
Planning retries add model calls; rejected candidates cause zero adapter calls.
Local latency measures synthetic execution, not remote inference performance.
Tokens and cost are undefined because scripted calls provide no usage/pricing.

The starting source snapshot and full command logs live under ignored
`dist/phase04/starting/` and `dist/phase04/`. The snapshot records starting Git
state and hashes before production edits. It is local, not a distributable
production/private-data artifact. All tracked new corpus data is synthetic.

Live trials were not authorized and were not run. Preserve the exact reviewed
synthetic environment, endpoint/model match, request/token/time/USD caps,
first-attempt failure records and no-fallback procedure in [PHASE03.md](PHASE03.md).
Do not read `.env` or use a production database to complete this evaluation.
