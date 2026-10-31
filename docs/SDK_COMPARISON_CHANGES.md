# Deterministic aggregate comparison changes

The explicit 2026-10-11 request to fix monthly percentage comparisons authorizes
this bounded extension. It supersedes earlier statements that all calculated
comparison deltas are future work; arbitrary formulas remain unsupported.

This document covers ungrouped `change`. The separately requested
[entity-decrease ranking](SDK_ENTITY_DECREASES.md) uses `decrease` for one
registered label identity and an additive metric; other grouped change remains
outside the contract below.

`ReportSpec.comparison_calculation` is `none` by default or `change` for a fixed
absolute/percentage comparison. Models select this operation and two permitted
periods; they supply no formula, denominator expression or result values. In
`change` mode, `period` is the current period and `comparison` is the reference
period. A supplied year can apply to both named months in the same comparison;
an absent year still requires clarification.

Scope: one registered fact, one or more registered numeric aggregates, two bounded
periods, table presentation, no dimension/time grouping or aggregate filters.
The row limit must fit both source period rows and all selected metric rows.
Ordinary user filters and mandatory policies apply equally to both periods.
Grouping, time alignment, percentage-point calculations, ranking by derived
values and arbitrary formulas are outside this extension.

The compiler and adapter still read two ordinary policy-bound aggregate rows in
one deterministic SELECT. No new SQL expressions/joins or database objects are
introduced. The engine requires exactly one complete row for each period label,
rejects truncated/malformed results, then calculates locally using bounded Decimal
arithmetic. Fixed output columns are metric label (including unit), reference
value, current value, absolute change, percentage change (%) and change status.
Provenance records both periods, selected measures, calculation and denominator.
The table preserves the period values, including SQL null aggregate semantics.

Absolute change is current minus reference. For a positive reference, percentage
change is `(current - reference) / reference * 100`, computed before presentation
rounding. Null operands yield null changes with `missing_value`; zero reference
yields a valid absolute change but null percentage with `zero_baseline`; negative
reference yields null percentage with `negative_baseline` because a signed growth
label would be misleading. Otherwise status is increase, decrease or unchanged.
These fixed statuses are localized without a model call. No missing duration is
silently treated as zero. Non-finite/unsupported result values fail closed.

Decimal values and the absolute change serialize as precise strings. The
percentage change is computed exactly, then rounded half-even to two decimal
places in the report, so every host receives a bounded value (for example
`37.89`, not the full 400-digit quotient). Source
decimal strings retain their existing exact display. Numeric float measures still
use the existing two-decimal presentation. Model context contains only permitted
business metadata/messages/specifications; execution results and calculated
changes never enter it. Persistent refinements/retries retain the selected
operation and existing access/revision/catalog checks.

Legacy stored specifications that lack the calculation field decode as `none`.
Live strict provider schemas require it; provider-neutral intent may omit its
constraint. An explicitly extracted `change` cannot be silently replaced by
ordinary period rows. Tests use synthetic values/fake model transport; live
artifacts remain in ignored local storage.

A bounded local vocabulary check retains explicit Persian/English percentage
change wording when intent extraction drops the operation. For comparisons of
two whole periods without requested breakdowns, it also prevents general
"monthly comparison" wording from becoming time grouping. Explicit breakdowns
remain intact and unsupported; an explicit removal of percentage display selects
`none`. This is a conservative conversation guard, not universal NL validation.

Verification commands:

```powershell
.venv/Scripts/python.exe -m pytest tests/test_sdk_comparison_changes.py -q
.venv/Scripts/python.exe -m pytest -q
node tests/web_tabs.cjs
.venv/Scripts/python.exe -m build --no-isolation
```
