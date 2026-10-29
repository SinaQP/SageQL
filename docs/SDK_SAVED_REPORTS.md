# Saved reports

A user saves a finished report once and re-runs it any time with **zero model
calls**: the SDK validates the saved definition, compiles SQL and reads fresh data.
Only the first, conversational run costs model tokens.

## What is stored

The public `ReportSpec` (registered concepts, the original period selection and the
filter values the user gave), a name, the owner (subject + tenant), the catalog
version and a timestamp. Never SQL, resolved lookup identities, policy values or
result rows. A name filter stays a name and is resolved again on every run.

## Dynamic dates

Relative periods (`last_month`, `this_month`, `rolling`, `last_jalali_month`,
`this_jalali_month`, `jalali_rolling`, …) resolve against the host's business date
on every run, so "last month" moves with the calendar. A report with fixed dates
can be made dynamic when saving (`period=PeriodSelection("last_month")`) or given
other dates per run. Comparison reports keep their saved periods.

## API

```python
saved = engine.save_report(session_id, report_id, actor, "ساعات ماهانه",
                           period=PeriodSelection("last_jalali_month"))   # optional
engine.list_saved_reports(actor)            # [{id, name, created_at, dataset_id, period, has_comparison}]
reply = engine.run_saved_report(saved["id"], actor,
                                period=None,   # optional PeriodSelection override
                                filters=None)  # optional tuple[UserFilter, ...] replacing saved filters
engine.delete_saved_report(saved["id"], actor)
```

`run_saved_report` returns a `Reply` (`report_ready`, `needs_clarification` when a
saved name became ambiguous, or an error) and is not stored in any session. The
report's provenance includes `saved_report_id`.

## Safety

Every run applies the caller's **current** policies, current catalog validation,
the explicit execution opt-in, timeouts and row limits, exactly like a
conversation report. Records are owner-scoped: other users cannot list, run or
delete them. Each owner may keep up to 100 saved reports.

Storage: `InMemorySavedReportStore` (default, lost on restart) or
`SQLiteSavedReportStore(path)`; pass it as `SageQL(..., saved_reports=store)`. The
Rahtal host keeps them in `.venv/rahtal-web/saved-reports.sqlite`.

## Web page

Under each conversation report: a name box, a period choice (keep the report's
dates, or previous/current month, last 7/30 days in the catalog's calendar) and
**ذخیره گزارش**. The **گزارش‌های ذخیره‌شده** panel lists saved reports with run and
delete buttons. Routes: `GET /saved-reports`, `POST /saved-reports`,
`POST /saved-reports/<id>/run`, `POST /saved-reports/<id>/delete`.

## Not yet

Shared/team reports, scheduled runs, input forms for filters, and reusing a cached
spec for a repeated question.
