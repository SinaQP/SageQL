# Changelog

## Unreleased

### Fixed
- Comparison reports round the percentage change half-even to two decimal places
  instead of returning the full 400-digit quotient; `calculate_change` stays exact.
- A model reply that declares an unregistered operation (with user-quoted evidence)
  but also carries an invalid concept or condition now returns `unsupported` with
  the operation message, instead of a generic "invalid reply, try again" error.

## 0.2.1 — 2026-10-30

First release published to PyPI (`pip install sageql`). No SDK behavior changes.

### Fixed
- CI: frozen evaluation inputs are hashed with LF-normalized line endings
  (`evaluations/frozen.py`), so the offline gate passes on any checkout; package
  jobs no longer hard-code the `0.1.0` archive names.

### Changed
- README rewritten around the design, measured results and an offline
  quickstart; the long feature description moved to `docs/CAPABILITIES.md`.
- Package metadata: author, keywords, classifiers and project URLs. README links
  are absolute so they work on PyPI.

### Added
- Tag-triggered PyPI release workflow using trusted publishing (no stored token).

### Removed
- The private Rahtal host (`sageql_rahtal/`), its dedicated tests and manual test
  guide are no longer published or packaged. Tests that use its catalog skip
  when it is absent.

## 0.2.0 — 2026-10-30

Cheaper, faster and more accurate report understanding, plus saved reports.

### Added
- **Saved reports**: save a finished report and re-run it with zero model calls,
  fresh data and moving dates (`save_report`, `list_saved_reports`,
  `run_saved_report`, `delete_saved_report`; in-memory and SQLite stores).
  See `docs/SDK_SAVED_REPORTS.md`.
- **Per-stage models and reasoning effort** on `OpenAIReportAgent`
  (`stage_models`, `reasoning_effort`) and per-stage token usage events.
- **`OpenAIReportAgent.recommended(config)`**: the measured cheap setup
  (mini intent, compiled spec, no reviewer call, low reasoning effort).
- **`compile_intent`**: a complete intent compiles locally, skipping the planner call.
- **`review=False`**: accept candidates that pass every local check without a reviewer call.
- **`intent_samples`**: optional parallel intent extractions with an agreement
  vote; one failed sample no longer fails the turn (live accuracy not yet measured).
- **Report interpretation**: each report lists the filters, conditions, sort and
  row limit it applied (`provenance["interpretation"]`), shown on the web page.
- **Rahtal test panel and guide**: 20 example questions with expected outcomes
  and read-only SQL cross-checks (private guide).
- **Live evaluation levels** (`smoke`, `standard`, `full`) with hard spending caps,
  per-model pricing, and a halt on HTTP 429.

### Changed
- Rahtal and the reference web host use mini intent, compiled spec, no reviewer
  call and low reasoning effort: 22/27 correct synthetic reports versus 6/27 for
  nano everywhere, ~7 s and usually one model call per turn.
- SDK defaults are unchanged for backward compatibility; use `recommended()`.

### Fixed
- Model output that filled controls marked "unspecified" with placeholder
  values is cleaned instead of rejected.
- A ranking with no chosen measure asks for it instead of sorting by a default metric.
- Report interpretation never shows identities resolved from name lookups.

### Removed
- Historical phase reports, procedures and versioned evidence (kept in git history).

### Known limits
- Released without the manual Rahtal real-data check; live checks cover the
  synthetic legacy cohort (21/21 turns correct).
- Native SQL Server behavior unverified; local workspace token instead of user login.
- No share-of-total, absence or per-group top-N operations; saved reports are personal.
