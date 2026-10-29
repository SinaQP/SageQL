# Phase 14 replacement contracts

V3 preserves every v2 question and expected answer and changes only eligibility
and exposure metadata for a **disabled** targeted approval packet. No execution
authorization or live result exists for V3. V1/v2 remain live-ineligible; the
historical description and first results below retain those versions' scope.

R01–R04 replace the development-exposed N01–N04 scenarios with different wording
and report requirements over the existing synthetic hosts. Questions and answer
keys are separate, frozen before their respective first execution. Expectations
use the existing independent Python/Decimal reference and manual date bounds.
The author knows the SDK, earlier corpora and fixtures; no externally blind
authorship or broad generalization claim is made.

These cases are **live-ineligible** and excluded from both approved N/A selections.
No API requests were authorized or executed for them. Reuse the existing runner:

```powershell
.venv/Scripts/python.exe -c "from pathlib import Path; from evaluations.phase08 import load_cases, safety_check; from evaluations.phase06 import run; root=Path('evaluations/phase14_replacements'); cases=load_cases('replacement', corpus_root=root, corpus_version='v2', cohort_prefix='phase14'); result=run(cases, Path('dist/phase14/replacement-contract-v2'), corpus_root=root, corpus_version='v2', turn_hook=safety_check); print(result['summary'])"
```

Use a fresh output directory on later invocations; preserve every first result.
This command defaults to scripted offline execution on disposable SQLite and
uses no model credentials or native SQL Server.

V1 and its first result are preserved: 6/6 supported reports, 2/3 conversations.
R02's negative-answer expectation used the historical author's obsolete generic
error code. V2 explicitly corrects that metadata to `clarification_stalled` and
adds the period-structure replacement R04. No V1 question or report answer changes.
V2 passed 9/9 supported reports and 4/4 conversations with scripted model outputs
on the final SDK. These figures measure the offline contract, not real-model
response quality. See the [Phase 14 report](../../docs/PHASE14_ENGINEERING.md) and
[V3 evidence](../phase14/verification.v3.json) for actual live failures and scope.
