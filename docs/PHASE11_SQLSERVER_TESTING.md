# Separately gated SQL Server synthetic verification

Phase 12 rechecked this procedure and its disabled approval gate. A later explicit
production read-only authorization led to one short, certificate-validated
connection attempt, which failed with 08001 before SQL. No retry, source read,
fixture operation or isolation change occurred. That separate assessment does not
enable this suite on production. See [the current status and coverage gaps](PHASE12_ENGINEERING.md).
The twelve prepared cases are reusable infrastructure, not complete native evidence.

Phase 11 has no approved real SQL Server target. This suite is prepared and its
approval validator is tested offline. It has not executed against a driver/server.
Real SQL Server execution remains unverified. Never substitute Rahtal credentials,
production configuration or an existing application database.

## Review before connection

An operator must separately approve the exact isolated server/database, driver,
authentication, network exposure, operations, fixture policy, cleanup and time
limits. Start from the disabled
[manifest template](../evaluations/phase11/sqlserver-approval.example.json).
The database must already exist with a `SageQL_Phase11_` prefix and contain only
synthetic fixtures. A prefix is an accident guard, not proof of authorization or
isolation: review the actual target. No test creates a database, enables snapshot,
grants permissions or changes production infrastructure.

The template is unauthorized. Replace its placeholders only after human approval;
keep reviewed configuration and credentials in ignored storage. The loader never
loads `.env` or falls back to application/Rahtal credentials. Full approval and a
separate confirmation are required before test credentials are read or the
optional driver is imported. Ordinary release checks remove these opt-ins.

## Operations and fixtures

`host_seeded` permits SELECT checks against the exact namespaced tables in
`tables.facts` / `tables.people`, with cleanup `leave_host_seeded_unchanged`.
DDL, seeding and concurrent writes are not implied.

`create_drop` requires explicit `create_fixture`, `insert_fixture` and
`drop_fixture` approval plus cleanup `drop_created_fixtures`. The suite creates
random `sageql_phase11_*` tables in the approved existing schema, seeds tiny fixed
records and drops only those generated objects, including after failure. Each
update/insert/delete schedule requires its own permission and is skipped for
host-seeded fixtures. No failed database operation is retried.

Host-seeded fixtures must match `Runtime.fixtures` in
[the helper](../tools/sqlserver_synthetic.py): tenant/deleted/owner, DATE,
DECIMAL(18,4), FLOAT, nullable NVARCHAR and DATETIME2 fact columns; and tenant/
deleted/id plus case-sensitive NVARCHAR profile labels. Visible amounts are
10.2500 and 20.5000, labels Ada and کیان نمونه; tenant/deleted records must remain
excluded. Unknown returned rows are not echoed into integration records.

The reader and writer must already have their reviewed permissions. Tests never
configure identities or permissions. SNAPSHOT must already be enabled/supported;
an unavailable capability is recorded/skipped without enabling it or downgrading.

## Run only after authorization

Install the optional ODBC extra and actual host driver. Use a fresh dedicated test
process with the already approved target and test-specific authentication:

```powershell
$env:SAGEQL_SQLSERVER_TEST_CONFIRM_PHASE11 = '1'
$env:SAGEQL_SQLSERVER_TEST_PHASE11_APPROVAL = 'ABSOLUTE_PATH_TO_REVIEWED_MANIFEST'
$env:SAGEQL_SQLSERVER_TEST_PHASE11_OUTPUT = 'ABSOLUTE_PATH_TO_NEW_RESULT_JSON'
python -m pytest tests/test_sdk_sqlserver_phase11_integration.py --run-sqlserver-integration -q
```

For SQL authentication, securely supply reader
`SAGEQL_SQLSERVER_TEST_PHASE11_USERNAME` / `_PASSWORD` and, when approved, writer
`SAGEQL_SQLSERVER_TEST_PHASE11_WRITER_USERNAME` / `_PASSWORD`. Do not paste
credentials into transcripts or tracked files. Integrated authentication uses the
approved process identity and does not manufacture a separate read-only user.
Pooling is disabled in this dedicated test process; production pool reset is not
certified by this suite.

Login/query timeouts are finite, at most five seconds. One runtime tracks the
reviewed suite budget, at most 120 seconds. Best-effort cleanup can use an
additional bounded connection after the business deadline to remove generated
objects. Python cannot forcibly stop a faulty/hung driver: retain host process/
workload limits and review residual fixture cleanup after interruption.

## Separate evidence categories

Read checks measure actual parameter binding, Decimal scale, float/null mapping,
Persian Unicode, DATE/DATETIME2 mapping, fixture collation, source policies,
grouping/order and cardinality. Independent writer commits/rollbacks occur at
explicit aggregate-to-label checkpoints. A snapshot factory selects ODBC
`SQL_COPT_SS_TXN_ISOLATION` / `SQL_TXN_SS_SNAPSHOT` before SQL; the SDK then checks
actual session/database settings. It never issues T-SQL transaction commands.

`waitfor_probe` separately authorizes a fixed five-second driver probe. Timeout
must return timeout SQLSTATE, not any arbitrary error. Cancellation also requires
`observe_sessions`: an approved observer waits for the actual server WAITFOR
checkpoint before canceling; successful cancellation requires cancellation
SQLSTATE. No fixed sleep is taken as proof that execute started.

`reader_denial_probe` authorizes one rollback-only INSERT attempt on the synthetic
profile fixture. It passes only on SQL Server's permission-denial code. The SDK
still executes canonical SELECTs only; raw fixed fixture/diagnostic statements
belong solely to this separately approved integration tool.

Server cleanup observation requires `observe_sessions` and approved SQL-auth
`SAGEQL_SQLSERVER_TEST_PHASE11_OBSERVER_USERNAME` / `_PASSWORD`, with the server
version's already granted DMV visibility. The observer checks that permission
before claiming zero matching sessions. Otherwise server cleanup remains
unverified even when driver close returns. External/distributed sources and
production pools require separate evidence.

Output records interpreter/platform, actual driver/server versions, approval
hash, scenario/isolation, expected/actual safe outcomes, contributing reads,
cleanup and executed/skipped/failed status. Credentials, connection strings,
private endpoints and unknown row values are excluded. Hosted CI and real SQL
Server tests remain unexecuted in this phase. Offline CI skips before reading
private configuration.
