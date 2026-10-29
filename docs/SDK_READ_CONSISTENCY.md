# Report read consistency — Phase 11 contract

This slice adds an explicit host option for a coherent database view across the
reads of one ready report. It does not change reporting operations, permissions,
model protocols, database configuration, or the default execution behavior.
No real SQL Server target/operations have been authorized for this phase.

Native verification remains blocked: a later
explicitly authorized production read-only connection failed with SQLSTATE 08001
before any SQL. The credentials file was unchanged; no retry or isolation change
occurred. The synthetic suite retains its disabled approval gate. Native snapshot
concurrency/cleanup remain unverified and are not authorized on production.

## Starting behavior and actual reads

`SageQL.submit` prepares a typed request after interpretation and validation.
An optional entity-name lookup executes one bounded SELECT. The main report
executes another SELECT. Selected entity-label dimensions then execute zero or
more bounded label batches. Registered relationships, duplicate-source guards,
period comparisons, matching-day counts and participant means are compiled into
the main statement; they do not independently open connections. Decrease ranking
and fixed comparison changes process complete query results locally.

Each existing adapter `execute` opens and disposes its own connection. SQL Server
first checks registered source metadata, then executes its canonical report
SELECT; it rolls back and closes afterwards. SQLite similarly verifies metadata
and executes a bounded read-only query on a fresh file connection. Existing
metadata verification itself therefore also issues statements. None of these
separate `execute` calls currently share a report-wide transaction.

The default SQL Server isolation/autocommit settings are inherited from the
trusted connection factory. The SDK cannot promise even a particular
statement-level isolation when that factory selects weaker isolation. Under
RCSI, version consistency is per statement, not per report. A concurrent commit
between lookup/main/label calls may produce a mixed-state report. A persistent
conversation and atomic session publication do not repair database read skew.

## Selected modes and alternatives

`SageQL(..., read_consistency="compatibility")` preserves the existing default:
normal per-execution connection ownership and the host/database's isolation.
New report provenance labels this mode explicitly; it makes no snapshot claim.

`read_consistency="snapshot"` requires an adapter `read_scope(limits, *, cancel)`
context manager. It yields an executor with the existing `execute` interface.
The engine passes that executor to **every** lookup, main query and label batch.
It closes the scope before accepting the report into session state and checks
current application access again. No transaction is held while calling a model
or waiting for a later conversational turn. A missing capability returns an
explicit unsupported consistency outcome; there is no fallback.

New artifacts receive `provenance.read_consistency` with the selected mode.
Older artifacts/receipts without that additive marker retain compatibility-mode
semantics and are not rewritten. The mode participates in strong-mode request fingerprints, so a compatibility
receipt cannot masquerade as a snapshot replay. Strong-mode saved-report
retrieval refuses older artifacts without that provenance. Legacy engines and
receipt fingerprints retain their behavior; a host changing modes should use a
new request ID to run a report with the newly requested guarantee.

A plain BEGIN wrapper around existing `execute` calls was rejected: those calls
would still open and roll back independent connections. Automatically choosing
SERIALIZABLE or enabling database-wide row versioning was rejected because it
changes workload/configuration policy. The chosen additive scope owns exactly
one disposable connection and reuses canonical validation/compiler/schema/result
paths. The old `DatabaseAdapter.execute` protocol remains sufficient in default
mode. Custom snapshot adapters explicitly assume the scope contract; the SDK
cannot verify the internals of arbitrary host code.

## SQL Server ownership and prerequisites

The host optionally supplies
`SQLServerAdapter(factory, snapshot_connection_factory=prepared_snapshot_lease)`.
The second factory must return a fresh, dedicated/disposable connection or tested
pool lease, with **autocommit=False** and **SNAPSHOT isolation already selected
through the appropriate ODBC attributes before SQL**. It must not return an
existing application transaction. Initialization/reset and finite login timeout
remain host responsibilities; the SDK does not adopt external transactions.

The scope verifies manual commit, the current session's SNAPSHOT level and the
current database's enabled snapshot state using a fixed bounded metadata SELECT.
Missing/incorrect/unverifiable settings fail closed. It never enables database
options or issues BEGIN/COMMIT/ROLLBACK T-SQL. Driver rollback ends the read
transaction, and close disposes the lease on success, clarification or failure.
One adapter concurrency slot is occupied for the whole scope. Every statement
gets bounded driver timeout/cooperative cancellation; no failed read is retried.

The guarantee covers versioned data from the same participating local database
transaction. Hosts must review trusted views and their underlying sources.
Linked servers, distributed/external/nonversioned data and arbitrary cross-source
transactions are outside this guarantee. DDL/metadata are not promised to be a
historical snapshot; concurrent schema changes can fail a report. A transaction
does not snapshot application authorization or cover unrelated connections.

Microsoft distinguishes [RCSI and transaction SNAPSHOT](https://learn.microsoft.com/en-us/sql/relational-databases/sql-server-transaction-locking-and-row-versioning-guide).
Its [ODBC transaction guidance](https://learn.microsoft.com/en-us/sql/relational-databases/native-client/odbc/performing-transactions-in-odbc)
requires driver transaction APIs for manual transactions, and
[SQLSetConnectAttr guidance](https://learn.microsoft.com/en-us/sql/relational-databases/native-client-odbc-api/sqlsetconnectattr)
identifies the SQL Server-specific snapshot isolation attribute. No real driver
behavior is certified by fake connections. Real SQL Server execution remains
unverified until the separately approved synthetic suite runs.

## SQLite ownership and differences

The built-in SQLite scope opens one read-only file connection, sets query-only
and trusted-schema safeguards, and starts one explicit read transaction before
registered metadata/data reads. The first read establishes its view. It resets
the allowlisted authorizer for each validated source set, retains a cumulative VM
budget, and rolls back/closes only when the scope ends. Fixed metadata/rollback
use a trusted callback; canonical business queries always install the registered
allowlist. This works on Python 3.10, where disabling an authorizer with `None`
is unsupported. Cleanup clears progress handling before rollback so cancellation
cannot prevent that cleanup. Read-only file/query-only mode stays in force.

The SDK never enables WAL. The host's fixture/configuration selects journal mode.
WAL permits a writer to commit while the reader retains its old view; rollback
journals can block writer commits for the read transaction's lifetime. The
[SQLite isolation documentation](https://www.sqlite.org/isolation.html) describes
these separate behaviors. A later report opens a new transaction and may see
new data. In-memory or multi-file/multi-connection snapshots are not added.

## Failure, security and resource contract

Scopes are request-local, thread-confined and invalid after exit or any failed
read. A caller cannot catch a failed statement and publish earlier partial data
as a successful scope. Limits/cancellation stay bound to the request; query
budgets cannot reset the whole-scope deadline. Every cursor closes, followed by
rollback and connection close. Cleanup failure prevents successful publication.
The SDK attempts cleanup even when earlier cleanup steps fail and exposes only
bounded safe errors. A broken/hung driver or factory cannot be forcibly stopped
by Python; actual server cleanup/cancellation still needs integration evidence.

Existing source/target policies and authorization checks remain outside the data
snapshot and apply before/after contributing reads, after cleanup, before
publication, and on saved/cached access. Snapshot isolation does not make policy
revalidation and a separate session store one atomic distributed transaction.
Ownership, revision guards, rollback to the previous successful report and
idempotency remain mandatory. No SQL, credentials, physical mappings, policy
values, resolved identities or result rows are added to model context.

Long-lived scopes occupy connections and may retain versions or locks. Request,
query, row, VM and concurrency bounds remain necessary. Synthetic test durations
do not establish production throughput or version-store capacity. A new request
may be issued after a transparent failure; the SDK never retries its database work.
