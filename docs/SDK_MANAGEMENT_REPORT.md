# Rahtal monthly workload report

User outcome: a manager can compare recorded workload in Shahrivar 1405 and
Mordad 1405 by current job position, then inspect employees with low recorded
hours in Shahrivar through the same persistent reporting conversation.

Acceptance: the configured interpreter preserves both explicit Jalali months,
SUM activity hours and activity count, registered grouping, requested sorting,
and subsequent aggregate threshold/top-N. Live report values must match a
separate local calculation over policy-bound registered source reads. The web
table must identify both periods and their execution bounds clearly. Real rows,
names, identities and credentials stay in ignored local files.

The first request is:

> مجموع ساعات فعالیت و تعداد فعالیت‌های ثبت‌شده در شهریور ۱۴۰۵ را با مرداد ۱۴۰۵ به تفکیک سمت شغلی فعلی کارکنان مقایسه کن. در جدول نشان بده و بر اساس مجموع ساعات از بیشترین به کمترین مرتب کن.

Follow-up requests:

> مقایسه را حذف کن. فقط شهریور ۱۴۰۵ را به تفکیک نام کامل کارمند و سمت شغلی فعلی، با همان دو شاخص، در جدول نشان بده.

> فقط کارکنانی را نشان بده که مجموع ساعات ثبت‌شده‌شان کمتر از ۸۰ ساعت است؛ ۱۰ نفر با کمترین مجموع ساعات را از کم به زیاد مرتب کن.

> همین ۱۰ نفر را فقط با شاخص مجموع ساعات، به تفکیک نام کامل کارمند، در نمودار ستونی نشان بده؛ سمت را از گروه‌بندی حذف کن و شرط کمتر از ۸۰ ساعت حفظ شود.

Recorded hours indicate recorded workload, not productivity or quality. The
employee report includes employees with activity in the selected period; it
does not infer employees with no records. Current profile position is not
historical position. Comparisons return separate period rows with one global
result cap, not paired top-N identities or computed growth rates.

No new tables, database objects, source operations, model-written SQL, arbitrary
formulas, authorization design or remote data services are introduced.

## Run the local check

```powershell
.\.venv\Scripts\python.exe sageql_rahtal/management_report.py --env-file D:/Coding/ZarProject/rahtal-be/.env
```

Omit `--env-file` to use the host's established configuration locations. This
command uses the configured real interpreter and SQL Server with explicit host
execution opt-in. It never substitutes sample data. Each run has a unique
ignored directory under `.venv/rahtal-web/management-report/`, containing private
session state, source/reply/spec JSON, diagnostics, a safe summary and a local
HTML preview. The preview is a verification artifact, not a new SDK export API.
Console progress contains statuses, counts and timings, never names/rows/secrets.

The oracle creates a host-only verification catalog over the same approved
columns. Bounded registered SELECTs read activity row grain and profile
dimensions/counts under the current policies. Fixed independent Gregorian
boundaries check the month resolver, and Python calculates grouping, hours,
counts, thresholds and top-N independently of the report's aggregate query.
The default source cap is 10,000 rows per read, within SDK bounds; SQL timeouts
and a shared cancellation deadline still apply. Truncation, duplicate source
grain or changed access fails the check. Initial tables must be complete;
intentional top-10 truncation is accepted only after matching complete-source
ranking. Reads are separate and do not provide a cross-source snapshot.

## Package corrections

The real first attempt incorrectly declared comparison of two explicit Jalali
months unsupported. Shared capability instructions now describe that supported
case, and a model's prose-only unsupported claim goes through bounded planning
and review instead of bypassing review.

Independent intent controls now constrain comparison, row filters, aggregate
thresholds, sort/direction and limit. Explicit removal differs from an
unspecified control. Lost or changed controls must be repaired before execution.
See [SDK_AGENTS.md](SDK_AGENTS.md) for optional provider-neutral compatibility.

An independent tied-ranking probe exposed selection drift when the model
reordered employee/position display columns. Metric ranking now breaks entity
ties by the registered label's identity before other category dimensions,
preserving the explicit primary sort and period/time ties. A reversed-column
table and the following name-only chart retain the same selected identities.
This does not sort by resolved names or change aggregate values.

Comparison titles and provenance identify both locally resolved periods. The
web table uses these captions while keeping stable `base`/`comparison` JSON
values, and displays both Gregorian execution ranges. Its Rahtal suggestion
fills the managerial request without bypassing normal interpretation.

## Verification (2026-10-09)

All four conversation turns passed against the configured real interpreter and
Rahtal SQL Server. Full specifications, month boundaries, grouping, hours,
counts, ordering, threshold and final selected employees matched the independent
oracle. The available qualifying employees were fewer than ten; the report did
not invent additional people. After the tie correction, the accepted real-model
specifications were replayed through the final compiler against the real sources
and matched the oracle again; this replay made no new model requests.

Offline verification: **971 passed, one optional synthetic SQL Server test
skipped**. Tests cover semantic-control drops/removals, malformed responses,
zero execution after exhausted repair, equal-hour rankings with reversed display
columns, source policies/grain/truncation, identical names, persistence, HTML
escaping and private progress. Interim Windows HTTP tests hit transient socket
aborts; focused reruns and the final complete suite passed.

JavaScript syntax and Git whitespace checks passed. Current sdist/wheel builds
passed with `--no-isolation`, and a fresh wheel-target installation/import check
passed using existing dependencies. A completely fresh dependency environment
was not verified. The updated authenticated local frontend was activated on
`http://127.0.0.1:8770`, with separate private state/token at
`.venv/rahtal-management-web/`; earlier hosts were preserved. Authenticated
session creation and the updated page passed a local HTTP check.

No database objects, production rows, credentials or remote data services were
created or changed. Existing checkout changes were preserved. No commit was made.

Suggested commit message:

```text
feat: add verified Rahtal workload reports and preserve SDK intent
```
