# Explicit Jalali month selections

The [authorized manager extension](SDK_MANAGER_REPORTS.md) supersedes this
original slice's non-goals for Persian ranges/years, relative periods and bounded
monthly buckets. Its date-only bounds, conversion boundary and validation apply.

This extension is requested for the second Rahtal company demonstration. It adds
one date-only period kind, `jalali_month`, to the existing report specification.
The host resolves its boundaries locally; a model never converts calendar dates.

## Contract and acceptance

`PeriodSelection("jalali_month", year=1405, month=6)` selects Shahrivar 1405.
The year must be an integer from 1300 through 1499 and the month an integer from
1 through 12. Booleans, missing fields, contradictory fields and unsupported
years are rejected. The first day is inclusive and the first day of the next
Jalali month is exclusive. The database still stores Gregorian date-only values.
The resolver uses the bounded Borkowski calendar algorithm, with independent
month-boundary checks against the Persian calendar in ICU through Node Intl.

The interpreter maps explicit Persian month names to the numeric month and
explicit year. A missing year requires clarification. A year without a month or
an ambiguous calendar still requires the appropriate missing business detail.
Farvardin through Esfand mean the Jalali calendar. The interpreter must never
substitute Gregorian September for Shahrivar or supply converted ISO boundaries.

A Jalali month supports ungrouped reports and daily Gregorian date grouping,
plus ordinary registered dimensions, filters and a comparison with one other
bounded period. Daily buckets remain Gregorian ISO dates in SDK table/chart JSON;
a presentation can display an additional, deterministic Jalali label. Jalali
week, month, quarter or year grouping is not implemented. To prevent a Gregorian
month bucket from being mistaken for a Jalali bucket, coarse time grouping is
rejected while a `jalali_month` period or comparison is selected.

Report provenance records the original Jalali selection alongside the exact
Gregorian execution boundaries. Refinements preserve the explicit year/month;
relative period freezing retains its existing behavior. Session ownership,
current policies, registered concepts, execution opt-in, parameterized SQL,
metadata verification and query/result/request limits are unchanged.

## Non-goals

There are no timestamp/timezone conversions, fiscal calendars, inferred years,
Jalali relative periods, arbitrary date formulas, new SQL expressions or database
objects. Source `TimeDefinition.calendar` remains `gregorian`. The historical
staged CLI is not extended. Model-written SQL and model-selected joins remain
unsupported.

## Verification

Offline checks cover all supported month boundaries against an independent
calendar implementation, leap Esfand and year rollover, invalid types/ranges,
deterministic bound SQL and mandatory policies, clarification continuation,
comparison, persistence and refinements. A live smoke test uses the existing
configured interpreter and Rahtal SQL Server only after these checks pass.

The calendar reference is the [Borkowski implementation maintained by
jalaali-js](https://github.com/jalaali/jalaali-js). Its upstream license is retained
with the adapted resolver. The supported year range is deliberately narrower
than the reference implementation's full calendar range.
