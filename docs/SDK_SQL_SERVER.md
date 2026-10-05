# Embedded SDK SQL Server execution scope

This is the scope and safety design for the new `sageql.sdk` adapter. It is separate from the existing Rahtal pilot. The SDK never accepts or executes a SQL string from a model or browser.

## Supported contract

The host registers a single physical table or trusted reporting view for each dataset. Registration lists physical columns/types, business metric IDs, dimensions, user filters, optional date-only time column, and a contract version. A report selects one dataset and combines registered metrics, dimensions, typed filters, Gregorian date bounds/grains, ordering, and a bounded limit. Comparisons return two labeled periods, not calculated deltas.

A report may also select only registered dimensions: the compiler returns bounded `SELECT DISTINCT` combinations with the same typed filters and mandatory policies. Such listings require table presentation, no time grouping, and no comparison. A dimension-only dataset is allowed; an entirely fieldless dataset or report is rejected. This supports employee-name lists without inventing an aggregate or allowing arbitrary columns.

The first adapter has no joins, arbitrary expressions, user-supplied SQL, cross-database names, timestamp timezone conversion, fiscal/Persian calendar conversion, or write operations. A developer-provided view can encapsulate reviewed business joins; its aggregate grain is the developer's responsibility. The compiler cannot verify that a view's business formula is correct. This boundary prevents the prototype's aggregate fan-out issue from being introduced by model-planned joins.

## Inputs and enforcement

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

Offline tests use fake providers and SQL Server connections, checking compilation, mandatory policies, denied IDs, metadata drift, type compatibility, ordered binds, cancellation, result limits, resource cleanup, sanitized errors, ownership, persistence, duplicate turns, refinements, and failed revisions. SQLite supplies an explicitly read-only reference for synthetic result correctness; it does not provide SQL Server's fixed-point arithmetic guarantees.

The separate SQL Server integration suite runs only on an explicitly configured synthetic test table/view, with known expected totals and two actor scopes. Set `SAGEQL_SQLSERVER_TEST_CONFIRM_SYNTHETIC=1`, `SAGEQL_SQLSERVER_TEST_CONNECTION`, and `SAGEQL_SQLSERVER_TEST_TABLE`; optional `SAGEQL_SQLSERVER_TEST_SCHEMA` and `SAGEQL_SQLSERVER_TEST_KIND` default to `dbo` and `TABLE`. The host seeds the fixture documented in `tests/test_sdk_adapters.py`; the test performs SELECTs only and never provisions/seeds a database. Run `python -m pytest tests/test_sdk_adapters.py -k opt_in -q`. Rahtal can then provide a local real-data smoke test within its approved catalog. Its credentials and reports remain ignored and local. Integration results must be reported separately from offline test success.
