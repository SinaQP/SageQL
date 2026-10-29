# SQLite-first automated testing

SQLite is SageQL's primary automated development and evaluation database. Ordinary
pytest, CI and evaluation commands use disposable synthetic data, scripted/fake
model transports and independent assertions. Neither a running SQL Server nor
production credentials nor a Rahtal `.env` is required. Both production database
adapters remain supported; this policy changes test execution, not host behavior.

## Run the existing offline workflow

Install the core/development dependencies in a development environment. Optional
OpenAI/ODBC packages and a native SQL Server driver are not needed for ordinary
tests. Dependency installation can require a package index; test execution itself
requires no external service.

```sh
python -m pip install -e '.[dev]'
python -m pytest -q
python -m evaluations --strict --output dist/checks/strict.json
python tools/release_check.py offline --source . --output dist/checks/all-gates/results.json
```

Use fresh evidence output paths. The release helper already runs the complete
pytest suite, dependency check, fourteen-schedule SQLite probe and all existing
strict/held-out/Phase 03–09 evaluation commands. It explicitly selects all
Phase 06–09 cohorts. Historical complete Phase 03 must retain exit 1 with exactly
D02/D03; the helper checks that classification. This is not an unexplained test
failure or a changed expected result. Original/corrected Phase 08 populations
remain separately versioned.

Evaluation commands default to scripted models and local SQLite even when model
configuration exists in the environment. Only their separately approved explicit
live mode can create a remote client. No live run is part of this workflow.
The existing GitHub runtime jobs call the same offline release helper; they do
not enable native SQL Server tests or require application secrets.

## Pytest's offline boundary

`tests/conftest.py` applies default guards before test collection/fixtures:

- External Python socket connections and DNS resolution fail; loopback remains
  available for the existing local HTTP/frontend tests.
- If pyodbc is installed, its real `connect` is blocked. SQL Server contract tests
  inject their existing fake drivers/connections instead.
- Known production `.env` locations cannot be opened, including the Rahtal
  fallback locations. Tests may create explicit fake configuration in `tmp_path`.
- Native cases are marked `sqlserver_integration` and skipped before their
  configuration fixtures unless the actual command supplies
  `--run-sqlserver-integration`. Inherited native environment variables,
  `PYTEST_ADDOPTS` or ini defaults cannot activate that mode.

These are test-process safeguards, not a production authorization mechanism or
general sandbox. Existing mock transports, source-policy validation and native
approval manifests remain necessary. The SDK's production connections, identity,
timeouts and SQL validation are unchanged. Release checks additionally remove
SQL Server/live-evaluation opt-ins from child environments.

## Reuse synthetic hosts and independent expectations

The existing builders already close seed connections explicitly and create
realistic fact/dimension data with excluded tenants, deleted/restricted rows,
date boundaries, missing relationships and null values:

| Reusable source | Data and purpose |
|---|---|
| `examples/multi_domain.py` | Retail sales/products and library circulation/holdings; registered relationships, lookups, labels and metrics |
| `evaluations/phase03_hosts.py` | Dispatches those builders and an independent workshop catalog/policy/record set |
| `evaluations/phase05_hosts.py` | Adds registered vocabulary using those same host definitions |
| `evaluations/reference.py`, `phase05_reference.py` | Independent source arithmetic/filter/group/order expectations; no SDK-generated answer oracle |
| `evaluations/scoring.py` | Decimal-aware field/type/row/order/completeness assertions and mutation-tested scoring |
| `tests/test_sdk_read_consistency.py`, `tools/probe_read_consistency.py` | Existing specialized WAL fixtures and deterministic writer checkpoints |

For new pytest cases, request `sqlite_host_factory`. Each call creates a new
database under that test's `tmp_path`, reuses the existing catalog/policy/seed,
and returns `path`, `catalog`, `policy` and a read-only `database` adapter:

```python
def test_report(sqlite_host_factory):
    retail = sqlite_host_factory("retail")
    library = sqlite_host_factory("library", wal=True)
    workshop = sqlite_host_factory("workshop")
    # Prepare a typed report using these catalogs and trusted synthetic policies.
    # Compare against independently authored expectations/reference arithmetic.
```

`wal=True` configures only that disposable fixture. No journal mode is globally
changed. File-backed databases support realistic separate reader/writer
connections; `:memory:` is not a substitute for these multi-connection schedules.
There is no need to migrate every specialized fixture or duplicate its records.
Use existing model scripts and scorers instead of deriving expected answers from
executed SQL, returned rows, reviewer approval or the implementation under test.

## Application behavior coverage

| Behavior | Existing offline coverage |
|---|---|
| Metrics, dimensions, filters, aggregate thresholds, ranking, relationships and cardinality | `test_sdk_adapters`, `test_sdk_relationships`, `test_sdk_entity_decreases`, participant/matching-day suites |
| Lookup ambiguity and policy-bound labels | Entity lookup/label suites; real SQLite reads |
| Clarification, negation, registered vocabulary, continuation and refinements | Phase 01–09 corpora and semantic/clarification suites with scripted agents |
| Ownership, tenants, current authorization and revocation | SDK, relationship, lookup/label, session and consistency suites |
| Durable sessions, revisions, idempotent replay and previous-report preservation | `test_sdk_sessions`, conversation and read-consistency suites |
| Query/result limits, cancellation, cleanup and publication failures | Adapter, execution, session and consistency suites |
| Calendar boundaries and fixed reporting operations | Gregorian/Jalali/calendar, comparison/decrease/participant/matching-day suites |
| HTTP/table/chart/report payloads | Local web/frontend tests and existing browser regressions |
| SQL Server syntax, parameters, schema/result contracts and failure routing | Existing deterministic compiler tests and fake ODBC/connection tests |

This is coverage of the current registered application contract, not proof of
every possible request or real-model generalization. Unsupported capabilities
remain explicit unsupported outcomes rather than invented test implementations.

## Snapshot and concurrency verification

Reuse `python -I tools/probe_read_consistency.py --output dist/checks/consistency.json`.
It uses actual SQLite WAL transactions and independent writer connections at
controlled checkpoints. No timing sleep establishes a committed state.

The fourteen checks cover both modes with unchanged data, committed update,
rolled-back update, conflicting-label insertion, deletion, cancellation between
reads and failure before labels. Compatibility read skew is an expected observed
limitation; those checks are not credited as correct business reports. Snapshot
reads retain one coherent view, and cancellation/failure publishes no partial
report. Existing tests also cover lookup/main/labels, multiple label batches,
relationships, authorization changes, request budgets, replay and cleanup.

WAL permits a writer commit while a reader retains its old view. Rollback-journal
readers can block a writer's commit. These mechanisms are SQLite-specific; no
production journal setting or SQL Server isolation option is changed by tests.

## Separate SQL Server-specific coverage

All thirteen existing native cases are preserved and disabled by default. After
separate isolated-synthetic-target authorization, use an explicit command flag
**in addition to** the original approval/configuration:

```sh
python -m pytest -m sqlserver_integration --run-sqlserver-integration -q
```

See [the prepared synthetic procedure](PHASE11_SQLSERVER_TESTING.md) for bounded
operations/fixtures/cleanup and [SQL Server coverage](SDK_SQL_SERVER.md) for the
older host-seeded read-only case. A flag alone does not supply authorization.
Never point these tests at Rahtal production or read its credentials for testing.
Normal pytest and CI continue exercising offline SQL Server contracts without
this flag. Native skips are not simulated passes. Earlier Phase 12 connection
failure and all Phase 01–12 evidence remain historical records.

## What SQLite cannot verify

SQLite results cannot certify SQL Server's native decimal precision/overflow,
money/datetime2 conversion, Unicode binding through ODBC, native collation,
SQL Server optimizer/index behavior, driver compatibility, TLS/login, effective
database permissions, RCSI/SNAPSHOT semantics, locks/deadlocks/version-store costs,
server-side timeout/cancellation/transaction cleanup or pool state reset. Fake
ODBC tests verify call contracts, not those native mechanisms. Production workload
capacity and live-model language quality also require their own evidence.

The SQL Server adapter remains available for explicitly configured production
hosts. SQLite-first automated testing does not change the selected production
backend or imply equivalence between the two databases.

## Audit and evidence

The starting suite reproduced 2,201 passes / 13 native skips. An inherited
synthetic Phase 11 opt-in then activated a native fixture without an explicit
pytest flag; the absent fake manifest failed before any driver/credential access.
Three focused tests reproduced both native paths and the missing explicit option.
A fourth reproduction caught activation through inherited `PYTEST_ADDOPTS`.
The new option, marker and default boundaries repair that test-infrastructure
gap without changing SDK behavior or native test expectations.

The final full suites pass **2,212 tests / 13 native skips** on Windows Python
3.12 and 3.10 and Ubuntu WSL2 Python 3.12. Two intermediate Windows evaluation
runs stopped with the existing `local_io` classification. Their partial journals
remain preserved; fresh diagnostic Phase 06 runs completed, and complete semantic
gates were rerun separately. The underlying OS cause was not established, and no
database retry or change to evaluation expectations was introduced. The evidence
distinguishes those interrupted runs from final completed checks.

Current measured results, source binding, commands and preservation checks are
recorded in [the SQLite-first verification record](../evaluations/testing/sqlite-first.v1.json).
Earlier frozen cases, references, expected outcomes and measurement files are
preserved; current runs use fresh ignored output directories.
