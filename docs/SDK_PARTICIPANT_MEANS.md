# Registered means per participating entity

The sixth Rahtal question authorizes this fixed aggregate over an existing fact
source. Hosts register `MetricDefinition(aggregation="sum_per_participant",
column=..., participant_column=...)`. The first column must be numeric and the
participant column a physical integer or text identity in the same dataset.
Neither column may be an imported relationship projection. Other aggregations
must leave `participant_column=None`. Models select the permitted business metric
ID; they never provide these columns, SQL, formulas or joins.

For each complete filtered group the deterministic compiler divides the sum by
the count of distinct non-null participant identities. A person with many rows
counts once; a zero-hour or null-duration activity still represents participation.
Inactive profiles do not enter the denominator. Existing SUM null semantics are
retained: all unknown durations yield an unknown mean. Any missing participant
identity makes the mean unknown because the actual denominator is unknown. Empty
groups or a zero denominator also yield null. Totals and known distinct counts
can still be displayed separately; unknown means are never substituted with zero.

The quotient is explicitly an approximate `number`: SUM over a float/REAL cast
divided by the guarded distinct count in SQL Server/SQLite. Integer division is
avoided. This does not add exact-decimal ratio arithmetic; ordinary decimal sums
and averages retain their existing types. Non-finite adapter values fail closed.

The aggregate uses the existing fact predicates, policy-bound registered
dimensional imports, cardinality guard and execution limits. It is evaluated
before aggregate filters, ranking and row limits, in each comparison/time bucket
when explicitly requested. It adds no cross-grain query or database object.
Permission to select the new metric is independent of permission to display its
source identities; permitted catalogs retain both compiler columns while model
metadata contains neither. Catalog fingerprints/versioning invalidate stale
saved reports under the existing checks.

Rahtal registers `average_participant_hours`: total activity hours divided by
distinct employees with activities in that group/period. Position grouping uses
the existing **current** profile position, not historical position at activity
time. Missing/inaccessible profiles remain an unknown-position group. Its mean
uses fact participation, not the profile universe or average activity duration.

The intent agent uses host selection phrases plus an explicit averaging word
from user messages to retain this requested metric locally even if extraction
omits it. A plain activity average over the same duration column is removed
unless the user also explicitly requests average activity duration. A fresh
request for one-period totals receives no extra time buckets unless the user
asks for a temporal breakdown. Refinements preserve existing grouping and metric
selection; removal wording must not add the metric back. This bounded vocabulary
normalization supplements model planning/review and does not claim complete
natural-language understanding. Without a matching registered concept, it cannot
invent a new measure or grant access.

Non-goals: model-selected formulas, arbitrary aggregate ratios, weighted means,
cross-source measures, historical/effective-date position inference, recursive
joins or expansion to employees without recorded activity.

Verification commands:

```powershell
.venv/Scripts/python.exe -m pytest tests/test_sdk_participant_means.py tests/test_rahtal_position_workload.py -q
.venv/Scripts/python.exe -m pytest -q
node tests/web_tabs.cjs
.venv/Scripts/python.exe -m build --no-isolation
```

Ordinary tests use synthetic SQLite sources and fake model transport. A separate
configured Rahtal model/SQL Server run and bounded host-only source verification
confirmed the exact question; private rows and values stay in ignored artifacts.
