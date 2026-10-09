# Registered reporting relationships

This extension is authorized by the request to support complex management
reports through a reusable pipeline, rather than a special-case job-position
report. It extends the earlier single-source contract.

The host registers directed many-to-one relationships between existing datasets,
their ordered equality key pairs (including composite tenant keys), and explicit
dimension/filter imports. A report still chooses one fact dataset and business
concepts. The model never chooses keys, join types, SQL, infrastructure or identity.
Several independent relationships can enrich a fact dataset. Measures remain at
the fact grain; independent fact-to-fact joins, arbitrary formulas, recursive
relationship paths and historical/effective-date joins are not inferred.

Related attributes filter source rows and define aggregate groups. Sorting and
ranking operate on complete groups before top-N. Relationships use policy-bound
left joins. Missing or
inaccessible dimension rows become null attributes; the existence of a related
capability never grants access to its source. Source key dimensions and imported
concepts require current permission. Both sides' mandatory policies apply.

The compiler groups each policy-bound dimension source by its registered keys.
An internal single-statement cardinality guard rejects multiple visible rows for
any non-null source key, including identical duplicates and groups outside the
returned top-N. It never picks a profile or multiplies fact measures. This is
deliberately conservative: even an unused duplicate key in an active source
blocks the report. Null keys never match. The guard and result run in the same
canonical SELECT; there is no separate preflight race. Empty results have no
totals to release. Hidden guard values never appear in report JSON or model input.

Schema verification, current access rechecks, execution opt-in, parameter/work/
time/row limits, cancellation and connection cleanup cover every active source.
No database objects are created. Host registration determines current versus
historical attribute semantics. The Rahtal profile mapping represents **current**
job position, not an employee's position at the activity date.

Acceptance: synthetic reports from multiple domains, multi-key/multi-relation
grouping, related filters, rankings after complete aggregation, policies on both
sides, denied dependencies, duplicate rejection, comparison periods, persisted
refinements, physical-data exclusion and both dialect compilers. Ordinary
single-source reports must retain their existing behavior.

## Reporting language and date windows

`ReportSpec.aggregate_filters` contains typed `AggregateFilter(metric_id,
operator, values)` conditions on selected metrics. They apply after aggregation
and before ranking/limits, including both comparison branches. Row filters and
mandatory policies keep their original pre-aggregation meaning. Unselected or
denied metrics, unknown operators, wrong types and duplicate predicates fail
validation. SQLite explicitly casts decimal threshold parameters to numeric
because aggregate results have no physical column affinity.

`PeriodSelection("rolling", count=N, unit=...)` supports day/week/month/quarter/
year with integer N from 1 through 1200. Days/weeks include exactly N days or
N seven-day weeks ending today. Months/quarters/years start at today's Gregorian
date shifted back by N calendar units, clamping the day at month end; the
exclusive end is tomorrow. For example 2026-10-09 and three months resolve to
2026-07-09 through 2026-10-10 exclusive. Complete previous calendar periods are
different; the SDK does not reinterpret rolling months as a previous quarter,
90 days or Jalali months. Models supply count/unit, never compute these dates.
Successful session refinements freeze resolved bounds as existing ranges.

Old persisted specifications without aggregate_filters or count/unit remain
decodable. New model response schemas require these fields; unrelated extras
remain invalid. Adding related capabilities changes the catalog contract and
may invalidate previously saved reports under existing catalog checks.

## Verification

Run the offline regression coverage with:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_sdk_relationships.py tests/test_sdk_rolling_periods.py -q
.\.venv\Scripts\python.exe -m pytest -q
```

The configured model interpreted employee ranking, refinement to current job
position and a >100-hour aggregate threshold with the same rolling three-month
period. A canonical SQL Server report against the existing Rahtal sources passed
with five groups; no rows/names/credentials are stored in this document.

Final offline verification: 51 extension tests, 861 total tests passed, one
opt-in synthetic SQL Server test skipped. The existing synthetic SDK demo passed.
The isolated build was blocked by PyPI timeouts; sdist/wheel construction with
installed build dependencies and fresh wheel target installation/public imports
passed. This does not verify a completely fresh dependency environment.
