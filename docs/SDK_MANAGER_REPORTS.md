# Managerial activity reports and Persian business dates

The 2026-10-11 request authorizes this extension to the existing registered
relationship and date-only calendar contracts. It supersedes the older statements
that relative Persian periods, Persian ranges/years and monthly buckets are
unsupported. It does not authorize arbitrary source discovery or model SQL.

## Business definitions

Daily entity reports can include the fixed [matching-day count](SDK_MATCHING_DAY_COUNTS.md).
For example, a typed condition on daily total hours identifies high-workload
days, and the added count states how many qualifying days each employee has in
the requested period. It counts grouped days, not activities, and runs before
detail-row limits. Other management reports retain the false default.

Hosts can register bounded `DatasetDefinition.description`, `default_metric_ids`
and `MetricDefinition.description`, `selection_terms` and `ranking_terms`.
Only permitted business metadata crosses the model boundary; denied defaults
are removed from projected catalogs. These fields grant no data access.

Rahtal defaults to **total recorded hours and activity count**, not average
duration. Average duration remains available for an explicit user request such
as «میانگین» or “average”. A local vocabulary guard checks the user's own words;
assistant suggestions do not count. New requests do not inherit old evidence.

The separately registered [participant mean](SDK_PARTICIPANT_MEANS.md) answers
average hours per employee with recorded activity in a group/period. It divides
total hours by distinct participating fact identities, not activity count or
the profile universe. Current-position reports use the existing policy-bound
profile mapping; historical positions are unavailable. Explicit averaging and
host selection phrases retain this measure locally if intent extraction omits
it; totals plus participant count alone do not fulfill the request.
Refinements may preserve a previously selected measure. For top-N rankings,
registered ranking terms also require a stated criterion before choosing hours
or activity count. Host-defined `ambiguous_ranking_terms` recognize fresh quality
requests that have no registered measure evidence and return a focused criterion
question without a model/data call. Short criterion answers retain the original
relative period through local conversation evidence; an explicit new date/month
in the answer takes precedence over that earlier window.
The exact locally generated criterion question identifies its answer even when
intent extraction mistakenly classifies that answer as a new report.
This guard is conservative business vocabulary validation, not a general proof
of natural-language intent or an invented productivity formula. Planner/reviewer
checks and typed intent constraints still apply.

The host registers the existing `core_titleactivity` id/name dimension and
`functionality_activities.title_id -> core_titleactivity.id` many-to-one mapping.
Topic grouping and equality/IN filters use this fixed mapping. Names are business
values returned by the report; database rows/names never enter model context.
The activity/profile soft-delete policies remain mandatory. The topic model has
no soft-delete column: the local administrator's topic scope has no invented
policy. A production host must register its own actual topic permissions.
Duplicate visible topic keys fail closed through the existing relationship guard.

Per-employee topic reports group by topic and employee identity before name
decoration. Topic totals can select the registered distinct `participant_count`
and filter it after grouping, e.g. >= 2 participants. That condition must not
be applied at topic/employee grain, where each identity group contains one
participant. A separate topic-total report identifies shared topics; this slice
does not add cross-grain subqueries for filtering the contribution breakdown.
Missing/inaccessible topics remain null groups so recorded hours are preserved.

Common questions addressed to the assistant's abilities receive a short locally
generated explanation for catalogs with defaults, without a model/data call.
Unrecognized capability wording can also receive it after intent extraction.
Successful replies name their measures, grouping, exact period
and metric sort. This does not interpret result rows or assert productivity.

## Date-only calendar contract

Monthly organization comparisons can select the fixed
[absolute/percentage-change operation](SDK_COMPARISON_CHANGES.md). The model
selects the two months and registered total-hour/activity-count metrics; the host
computes changes locally and presents both month values. A shared supplied year
applies to both named months in the same comparison. Plain monthly comparisons
without requested changes retain their existing two-period-row presentation.

`ReportingCatalog.preferred_calendar` is host-owned, either `gregorian` (default)
or `jalali` (Rahtal). It guides unspecified business periods and presentation;
an explicitly requested Gregorian period remains supported. Storage and SQL
continue to use Gregorian dates, with the host business clock in Asia/Tehran.

In addition to explicit `jalali_month`, period kinds include:

| Kind | Fields and meaning |
| --- | --- |
| `jalali_year` | Explicit integer year 1300..1499; full Persian year |
| `jalali_range` | Persian `YYYY-MM-DD` start and end, **both inclusive** |
| `this_jalali_month`, `last_jalali_month` | Full current/previous Persian month |
| `this_jalali_year`, `last_jalali_year` | Full current/previous Persian year |
| `jalali_rolling` | Integer count 1..1200 and day/week/month/quarter/year unit, through today |

Day/week rolling periods contain exactly N days/N seven-day weeks ending today.
Other rolling periods shift today's Persian date by the registered number of
months, clamping the day to the target month's final day. The exclusive end is
tomorrow. Resolved bounds must stay within the supported Persian years; an
exclusive end may be Nowruz 1500. Invalid dates and non-leap Esfand 30 fail closed.
An explicit named month without its year still requires clarification. Models
select original Persian dates/year/month or relative operations; they never
compute Gregorian conversions. Common single relative phrases such as «یک ماه
گذشته», «شش ماه اخیر» and «ماه قبل» are mapped locally to typed rolling or
complete-period operations before planning. Persian/Arabic digits are normalized;
explicit Gregorian wording overrides the host default. Monthly calendar
selections follow the host preference unless Gregorian grouping
is explicit; an existing Gregorian monthly report keeps its grain on refinement.
Multiple relative phrases and
comparisons remain structured interpreter decisions. References to unchanged
saved periods preserve frozen dates. A regrouping with no new date evidence also
restores the saved period if intent extraction invented a different window.
For a fresh time series over a stated rolling window, an absent output-count
request retains the standard 100-row cap. A six-month period must not silently
become a six-row cap: it can intersect seven Persian month buckets, including
partial first/current months. Explicit point/group counts remain separate.
`jalali_range`'s inclusive end differs explicitly
from existing Gregorian `range`'s exclusive end.

`time_grain="jalali_month"` requires bounded report/comparison periods whose
union intersects at most 120 distinct Persian months. The compiler builds a
fixed month-boundary CTE using bound Gregorian dates, then groups source rows
by those complete calendar month starts before aggregate filters/ranking/limits.
Boundary rows belong to exactly one bucket; partial first/last months include
only rows within the report period. Independent comparison periods do not
require intervening months. Both SQLite and SQL Server retain deterministic
parameter order, source policies, cardinality guards and adapter limits.
This calendar CTE is the only new join shape: models cannot choose its predicates
or supply a calendar table. Gregorian coarse buckets are rejected for explicitly
Persian periods to avoid presenting them as Persian months. Persian weeks,
quarter/year buckets, timestamps and arbitrary expressions remain unsupported.

Explicit Persian periods persist unchanged. Relative periods freeze to resolved
Gregorian ranges after success, including monthly bucket reports, so a later
refinement cannot silently move the reporting window. Report provenance includes
original Persian selections, exact Gregorian bounds, a local period caption and
the preferred display calendar. JSON date values remain Gregorian date-only
values. The frontend uses UTC date-only Intl Persian formatting for display,
retains Gregorian execution bounds, and rounds displayed floating-point measures
to two decimals without changing report data or fixed-point decimal strings.

An optional local agent observer records intent/plan/review stages, attempt
numbers, selected business IDs, missing-slot names, reviewer approval,
chart/grain/limit selections and fixed
intent-mismatch codes. It records no question/model prose, filter values or rows;
observer failures cannot change reporting. These events use the existing private
Rahtal diagnostics, never an external telemetry service.

Catalog changes invalidate saved reports through the existing fingerprint checks.
Restart the host and start a new chat after updating.

## Verification

```powershell
.venv/Scripts/python.exe -m pytest tests/test_sdk_manager_reports.py -q
.venv/Scripts/python.exe -m pytest -q
node tests/web_tabs.cjs
.venv/Scripts/python.exe -m build --no-isolation
```

Synthetic coverage exercises topic contributions/shared-topic counts, mandatory
source policies, denied dependencies, duplicate topics, aggregation before top-N,
leap/day/year bounds, Persian monthly SQL in both dialects, comparisons,
persistence and false average/ranking selections with fake model transport.
Ordinary tests send no network requests and use no real result data.
