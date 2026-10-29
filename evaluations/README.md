# Reporting evaluations

Offline evaluations run the public SDK end to end (intent, planner, reviewer
decoding, both SQL compilers, read-only SQLite, sessions, cached receipts) on
synthetic hosts with scripted model responses. No credentials, internet or SQL
Server are needed; pytest blocks sockets. Live runs are separate, explicitly
approved commands.

## Layout

| Path | Purpose |
|---|---|
| `runner.py`, `trajectories.py`, `scoring.py`, `reference.py` | Shared scenario runner, multi-turn trajectories, outcome scoring, independent Decimal reference calculations |
| `phase03_hosts.py`, `phase05_hosts.py`, `phase05_reference.py` | Synthetic retail/library/workshop host builders and references, reused by many SDK tests |
| `phase06.py`, `phase06_runtime.py`, `phase06_transport.py` | Durable runner: journal, budgets, approval validation, usage accounting, observed transport |
| `phase08.py`, `phase14.py` | Frozen-corpus loaders and selections (`legacy` A01–A12, `independent` N01–N06) |
| `model_comparison.py` | Live per-stage model comparison over the frozen Phase 14 selections |
| `phaseNN/` | Frozen questions (`cases.vN.json`), answer keys (`expectations.vN.json`) and hash manifests (`freeze.vN.json`) |
| `cases.json`, `baseline.json`, `baselines/` | Strict regression corpus and its recorded baseline |

The `phaseNN` names are historical; corpora are frozen and hash-checked, so a
changed question or answer needs a new version file, never an edit in place.

## Offline commands

```powershell
.\.venv\Scripts\python.exe -m evaluations --strict
.\.venv\Scripts\python.exe -m evaluations.phase14 --cohort legacy --output dist/eval/legacy
.\.venv\Scripts\python.exe -m evaluations.phase14 --cohort independent --output dist/eval/independent
.\.venv\Scripts\python.exe -m pytest tests/test_evaluations.py tests/test_phase14_evaluations.py -q
```

Exit codes: `0` matches the baseline/expectations, `1` differs (or known
incompletions remain), `2` cannot start. Outputs go to ignored `dist/`.

## Live model comparison

Needs explicit user approval (provider, models, cases, spending cap), an enabled
approval packet and `SAGEQL_EVAL_API_KEY` in the child process only.

```powershell
python -m evaluations.model_comparison --setup B --cohort legacy --output dist/comparison/B-legacy --prepare-approval dist/comparison/approval-B-legacy.json --authorization-id "<who approved, when, cap>" --observed-at 2026-10-29T11:00:00+03:30
python -m evaluations.model_comparison --setup B --cohort legacy --output dist/comparison/B-legacy --approval dist/comparison/approval-B-legacy.json
```

Packets bind exact source/evaluator/corpus hashes, endpoint, models, prices and
limits; any source change needs new packets. Wrong synthetic reports are scored
without stopping; isolation failures and denied reads stop the run; dropped
connections fail only their turn and are never retried. Latest results:
[docs/MODEL_COMPARISON_NANO_MINI.md](../docs/MODEL_COMPARISON_NANO_MINI.md).

## Outcomes

| Outcome | Meaning |
| --- | --- |
| `correct_report` | Checked spec, exact data/order/fields, dates, presentation and invariants match. |
| `correct_clarification` | The fixture requires clarification and the reply asks for the expected detail. |
| `correct_unsupported` | An unavailable capability is explained, with no report or reads. |
| `correct_denial` | An unauthorized request gets `access_denied` without reads. |
| `correct_block` | Deliberately invalid output fails with the expected safe validation code. |
| `incorrect_rejection` | A supported/clarifiable request gets the wrong refusal, question or block. |
| `semantic_error` | A report was returned with wrong selections, values, grouping, order or presentation. |
| `incomplete` | Required fields absent, unexpected truncation or inconsistent partial publication. |
| `operational_failure` | Provider/database/request failure; never credited as completion. |
| `unexpected_report` | A report was published where the fixture expected clarify/refuse/deny/block. |

Rates always carry numerator and denominator; empty populations report `null`.
Scripted latency is not a model SLA, and offline success is never a live result.
