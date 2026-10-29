# Embedded SDK SQL Server execution scope

Optional [host-owned value vocabulary](SDK_VALUE_VOCABULARY.md) resolves registered
aliases locally into existing typed predicates. It adds no value SELECT, resolver,
SQL expression or relationship; canonical values use ordinary bound parameters
under the same current source policies. Registration is not permission.

This is the scope and safety design for the new `sageql.sdk` adapter. It is separate from the existing Rahtal pilot. The SDK never accepts or executes a SQL string from a model or browser.

The additive [read-consistency contract](SDK_READ_CONSISTENCY.md) covers one
report's lookup, main query and label batches. The default remains
`read_consistency="compatibility"`. A host may request `"snapshot"`; SQL Server
then requires an explicitly supplied, prepared manual-commit SNAPSHOT factory.
Unavailable capability fails transparently; database options are never enabled.
See the [separately gated synthetic suite](PHASE11_SQLSERVER_TESTING.md).

The [Phase 12 native assessment](PHASE12_ENGINEERING.md) includes one subsequently
authorized production read-only connection attempt. It failed with SQLSTATE 08001
before SQL execution; `.env` was unchanged and no retry or TLS relaxation occurred.
Native types, read-only permissions and isolation metadata were not obtained.
Snapshot concurrency/cancellation/full cleanup tests still require an approved
isolated environment; the mutation suite remains disabled on production.

## Supported contract

The [matching-day extension](SDK_MATCHING_DAY_COUNTS.md) adds one fixed window
count to bounded daily entity tables. The canonical SELECT applies aggregate
conditions before counting filtered daily groups per registered identity/period,
then applies TOP/LIMIT. It uses the existing fact queries and policy-bound label
reads, with no new joins or model-selected window/partition expressions. False
is the additive flag's default, retaining ordinary SQL and result shapes.

The fixed [participant mean](SDK_PARTICIPANT_MEANS.md) registers numeric amount
and integer/text identity columns on the same physical fact. Its canonical
aggregate uses a floating SUM, distinct count, guarded division and a missing-ID
CASE. Both columns remain host-owned and absent from model metadata. It retains
fact/source policies, registered relationship guards and group-before-limit
ordering; arbitrary aggregate ratios remain unsupported.

The [manager extension](SDK_MANAGER_REPORTS.md) adds the fixed Rahtal activity-topic
mapping and date-only Persian periods/monthly grouping. Monthly grouping uses a
bounded locally generated month-boundary CTE with bound dates; no model-selected
calendar tables or predicates are permitted. Existing execution guards still apply.

The host registers a single physical table or trusted reporting view for each dataset. Registration lists physical columns/types, business metric IDs, dimensions, user filters, optional date-only time column, and a contract version. A report selects one dataset and combines registered metrics, dimensions, typed filters, Gregorian date bounds/grains, ordering, and a bounded limit. The adapter returns two labeled comparison periods. The bounded [comparison-change extension](SDK_COMPARISON_CHANGES.md) can calculate fixed ungrouped absolute/percentage changes locally afterwards; it adds no SQL expressions or joins.

The [registered relationship extension](SDK_RELATIONSHIPS.md) extends this
baseline with explicit host-defined dimensional mappings. A fact may import
dimensions and filters from several policy-bound sources. Compilation uses
registered equality keys, grouped dimensional CTEs, left joins and internal
duplicate-key guards. Metadata verification includes every active physical
source; virtual imported columns are never looked up on the fact table. The
SQLite reference authorizer allows only these registered physical sources.
Aggregate filters run after grouping and before the outer limit. Rolling date
windows use bounded count/unit selections resolved locally.

Default execution remains a SELECT under each host connection's isolation.
Opt-in snapshot execution shares one prepared connection and transaction across
contributing reads, then rolls back/closes before session publication. Host
initialization and pool reset remain required; RCSI alone is not a transaction
snapshot. Actual SQL Server execution remains unverified in this Phase 11 work.

A report may also select only registered dimensions: the compiler returns bounded `SELECT DISTINCT` combinations with the same typed filters and mandatory policies. Such listings require table presentation, no time grouping, and no comparison. A dimension-only dataset is allowed; an entirely fieldless dataset or report is rejected. This supports employee-name lists without inventing an aggregate or allowing arbitrary columns.

The separately scoped [registered entity lookup](SDK_ENTITY_LOOKUPS.md) supports
name-based activity requests. A host-declared full-name equality filter uses fixed
concatenation and normalization over one to four registered text columns. The
engine reads up to two distinct candidate identities with current source policies,
then binds a unique identity to the registered target equality filter. These are
separate single-source SELECTs with ordinary adapter bounds. Compatibility mode
has separate connection lifetimes; snapshot mode covers both under its documented
prerequisites. They are not a join or a distributed snapshot. Ambiguous/truncated matches
never select the first row. Lookup rows/IDs do not enter model context.

The adapter accepts only registered dimensional joins and rejects arbitrary expressions, user-supplied SQL, cross-database names, timestamp timezone conversion, fiscal calendars, and write operations. The [explicit Jalali month extension](SDK_JALALI_MONTHS.md) resolves one supplied month/year locally to ordinary Gregorian date bounds before compilation; it adds no calendar SQL expressions or Jalali time buckets. A developer-provided view can encapsulate reviewed business joins; its aggregate grain is the developer's responsibility. The compiler cannot verify that a view's business formula is correct. Models cannot introduce aggregate fan-out by inventing joins.

## Inputs and enforcement

The separately scoped [entity-decrease extension](SDK_ENTITY_DECREASES.md) reads
complete bounded period/identity groups with the host candidate cap, independently
of the output limit. Source truncation fails closed. Fixed local alignment/loss
ranking precedes the final output limit and separate policy-bound name reads;
it adds no SQL formulas, joins or database objects.

The host authenticates the user and supplies `ActorContext`. A required policy callback returns the datasets and concepts this actor may use, plus mandatory row conditions. Missing required identity must be rejected by this callback. User filters and mandatory policy predicates are separate; the interpreter sees only permitted business metadata and messages. Compiler-only columns and policy values are excluded from model metadata.

The engine checks session ownership, scope, versions, revisions, and idempotent request IDs. It validates the complete report specification against the registered dataset and current scope before compilation, rechecks policy immediately before and after execution, and denies saved reports when their catalog or scope no longer matches. Old reports do not bypass authorization.

The adapter revalidates the complete resolved specification, renders a canonical parameterized SELECT using fixed permitted operations, parses it as T-SQL SELECT, and executes only that rendering. It quotes registered identifiers and binds typed scalar values and exact date bounds in placeholder order. Every comparison branch includes the same mandatory policy conditions. It verifies only registered live table/view columns and compatible SQL types before sending the report query; live metadata never adds new allowed objects.

Compiled statements are limited to 2,000 bound parameters for SQL Server and 900 for the portable SQLite reference. SQL Server text reporting uses modern VARCHAR/NVARCHAR/CHAR/NCHAR columns; legacy TEXT/NTEXT columns are rejected by metadata verification. SQL aggregates preserve their normal null rules: an ungrouped SUM on no matches returns one null row, while COUNT returns zero. A null aggregate does not prove that there were no source rows, so it is not labeled an empty grouped result.

Use a dedicated reporting credential with the database permissions appropriate for the registered datasets. Write permissions alone do not cause the SDK to refuse an otherwise validated SELECT. Database permissions and optional database-native row security provide additional enforcement. The SDK does not configure SQL Server security policies or session identity itself.

## Bounds and ownership

The developer supplies a connection factory with a finite connection/login timeout. It must return a disposable connection or a pool lease whose cleanup is correct, never an existing application transaction. The adapter owns cursor cleanup, rollback, and closing this handle. Each report receives driver query timeout, cooperative deadline/cancellation checks, a concurrency bound, SQL result bounds, and a returned-row cap with truncation reporting.

A result cap does not bound the work needed to aggregate source rows. ODBC cancellation is driver-dependent, and Python cannot forcibly terminate a hung driver or a connection factory that ignores its timeout. Hosts must configure database workload limits and infrastructure timeouts where required. Identity state in pooled connections requires a separate tested initialization/reset design; this SDK does not automatically set session context.

No credentials, connection strings, returned row data, or raw driver/model errors are emitted in public errors. The package has no default telemetry or transcript logging. Persistent sessions contain report rows and messages and require host-controlled storage permissions and retention. The frontend reference server is loopback-only and is not a production authentication/deployment service. Its explicitly selected Rahtal mode uses a fixed local reporting principal over the existing approved employee/profile and activity sources, with a separate workspace token; it creates no database objects and does not reuse the offline interpreter.

## Verification gates

The separately scoped [entity-label dimension](SDK_ENTITY_LABELS.md) performs
post-aggregation display enrichment through bounded profile SELECTs. It does
not change the single-source compiler or enable model-selected joins. Source
and target policies, metadata verification and request cancellation apply to
all reads; duplicate profiles never multiply target aggregates.

Offline tests use fake providers and SQL Server connections, checking compilation, mandatory policies, denied IDs, metadata drift, type compatibility, ordered binds, cancellation, result limits, resource cleanup, sanitized errors, ownership, persistence, duplicate turns, refinements, and failed revisions. SQLite supplies an explicitly read-only reference for synthetic result correctness; it does not provide SQL Server's fixed-point arithmetic guarantees.

The separate SQL Server integration suite runs only on an explicitly configured synthetic test table/view, with known expected totals and two actor scopes. Set `SAGEQL_SQLSERVER_TEST_CONFIRM_SYNTHETIC=1`, `SAGEQL_SQLSERVER_TEST_CONNECTION`, and `SAGEQL_SQLSERVER_TEST_TABLE`; optional `SAGEQL_SQLSERVER_TEST_SCHEMA` and `SAGEQL_SQLSERVER_TEST_KIND` default to `dbo` and `TABLE`. The host seeds the fixture documented in `tests/test_sdk_adapters.py`; the test performs SELECTs only and never provisions/seeds a database. After separate synthetic-target authorization, run `python -m pytest tests/test_sdk_adapters.py -k opt_in --run-sqlserver-integration -q`. Ordinary [SQLite-first tests](SQLITE_FIRST_TESTING.md) never use Rahtal production or its credentials. Native integration results must be reported separately from offline test success.
