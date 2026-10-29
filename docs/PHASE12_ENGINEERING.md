# Phase 12 — Native SQL Server integration status

## 1. Executive summary

**Level A: Native verification remains blocked.** The user subsequently authorized
one limited production read-only assessment using the existing Rahtal settings.
The connection attempt failed with SQLSTATE **08001 before any SQL was issued**.
No native reporting/type/snapshot claim or full Phase 12 completion is established.
Phase 13 has not started.

The authorized `sageql_rahtal/.env` was read locally and remained byte-identical.
Credentials, endpoints and connection strings were never printed or retained in
evidence. Model settings were not used. There was one connection attempt, zero
SQL statements, zero business-source reads and no retry. Fixture writes, stress,
concurrency and cancellation experiments remain prohibited on this live target.

The existing Phase 11 integration infrastructure is retained. Its missing-
confirmation and disabled-manifest gates were directly exercised offline before
any credentials, driver import or network access. No replacement framework or
production SDK correction was introduced. The [original blocked record](../evaluations/phase12/verification.v1.json)
retains its historical authorization state; the additive
[read-only follow-up record](../evaluations/phase12/verification.v2.json) records
the later authorization and failed connection without rewriting v1.

## 2. Verified baseline

Started on `main`, revision `b74c10974265dcac522b3e23623e0f4f9a8ae582`, empty
index, 23 tracked modifications and 218 untracked files. All 348 starting
nonignored files were copied and hashed in `dist/phase12/starting/` before edits.
Prior uncommitted work, frozen cases, expected results and measurement records
remain intact. No reset, clean, rebase or overwrite of earlier evidence occurred.

The starting full suite reproduced **2,201 passed / 13 skipped**, 70.08 seconds,
exit 0. The package still contains 45 Python modules, with source digest
`460eb7424baaf5d0e86235b9803eb96faf98a3de6e43bd6651cdb2b951aeef8e`.
The digest covers sorted package-relative Python paths followed by file bytes.
This is the exact SDK source verified in Phase 11; no runtime source changes are
part of Phase 12. Environment versions and command/log bindings are in the record.

The read-only follow-up started with 350 nonignored files, 23 tracked modifications
and 220 untracked files at the same revision and empty index. Their hashes and
the pre-update documents are preserved in `dist/phase12-production-readonly/attempt-01/`.

## 3. SQL Server authorization and target

The target is live business data. The later explicit human authorization permits
only a bounded read-only connection, necessary metadata and independently safe
registered-source SELECTs. Business reads require independently verified read-only
access and safe execution cost. It does not authorize fixture tests, writes, isolation
changes, permission changes, retries or intrusive cancellation. The existing
[example manifest](../evaluations/phase11/sqlserver-approval.example.json) remains
`authorized: false`. Neither its confirmation flag nor its contents were weakened.

Still required before the full native suite: an explicitly approved isolated server and
`SageQL_Phase11_*` database, authentication/driver, network and verified TLS policy,
reader/writer permissions, fixture namespace/operations/cleanup, isolation settings,
execution/resource limits and any permitted DMV diagnostics. An administrator
must provision/configure that environment separately. The existing suite does not
create a database, grant rights or enable row-versioning options.

The direct gate audit observes two cases: absent confirmation returns before any
manifest read; confirmation plus the disabled public template raises the explicit
authorization error. Credential environment reads, driver import attempts and
network attempts are all zero in this audit. The separately invoked native suite
collects and skips all twelve cases. Its exit 0 is successful gating, not native
verification. Production read-only authorization does not enable that suite.

The one production attempt used the configured server/database/login only, a
three-second login timeout, a two-second query timeout, autocommit and no pooling
or connection retry. TLS encryption and certificate validation were required;
certificate trust was not bypassed. The ODBC access-mode hint is advisory, not
permission proof: [Microsoft documents that drivers need not prevent writes](https://learn.microsoft.com/en-us/sql/odbc/reference/syntax/sqlsetconnectattr-function).

Only a fixed single current-database/session metadata SELECT was prepared. It
would compare the configured database through a bound parameter and inspect
effective broad rights before any source read. Broad write/control rights or
unverified read-only enforcement would block subsequent probes. No privilege was
inferred from a username or `ApplicationIntent` setting. The prepared SELECT was
never dispatched because `pyodbc.connect` failed.

## 4. Native driver and type verification

No connected server product version, edition, compatibility level, collation,
driver binary/version, encryption state or permissions were observed. These fields
remain null/unverified in the results. Installed pyodbc 5.3.0 package metadata is local
software inventory only; it proves neither connectivity nor driver behavior.

The configured driver was available locally, but no connected driver information
was obtained. The attempt recorded SQLSTATE `08001`, which means the client could
not establish a connection ([ODBC reference](https://learn.microsoft.com/en-us/sql/odbc/reference/syntax/sqldriverconnect-function)).
The probe took 1.75 seconds overall. The sanitized code alone does not distinguish
network, certificate/TLS, endpoint or other connection causes; no root cause or
SDK compatibility defect is asserted. Raw driver diagnostics were discarded
because they can contain private endpoint or authentication details. No second
attempt or relaxed-TLS fallback was made.

Inspection of the existing suite confirms a prepared native scalar check for
Decimal scale, float, null, DATE/DATETIME2, Persian Unicode, case-sensitive fixture
collation and parameter binding, plus a policy-bound labeled aggregate report.
None of its native expected rows/types were observed in Phase 12.

## 5. Snapshot isolation

The existing contract remains [explicit and opt-in](SDK_READ_CONSISTENCY.md).
One host-prepared manual-commit lease must cover contributing reads; the SDK checks
the session SNAPSHOT level and database capability and rolls back/closes before
publication. Compatibility mode retains separate executions. RCSI alone is not
a transaction-wide snapshot. No isolation setting or default mode changed.

The scope, factory ownership, metadata checks, parameter binding, deadlines and
publication/replay paths were inspected. Their source and offline tests remain
verified; actual SQL Server transaction behavior remains unexecuted. SQLite and
fake-driver outcomes are not substituted for native observations.

## 6. Concurrency coverage and outstanding native cases

| Existing integration coverage | Native status |
|---|---|
| Committed update, rolled-back update, insert, delete; each in both modes | Eight cases skipped |
| Independent writer mutation at aggregate-to-label checkpoint | Prepared; not observed |
| Scalar/policy/Unicode labeled report without a writer | One compatibility case skipped |
| Fixed driver timeout and checkpoint-triggered cancellation | Two cases skipped |
| Explicit reader write-permission denial | One case skipped |

The prepared twelve cases do **not** establish every Phase 12 requirement even
when enabled. Additional approved native observations would be needed for a
dedicated unchanged snapshot schedule, controlled unsupported isolation, lookup
and relationship/comparison paths, SDK-scope cancellation/later-read/publication
failures, metadata/login timeout, permission revocation/replay and any claimed
pool reset. Expand the existing suite only as justified by the approved scope and
native execution; do not treat these gaps as new passing or failing measurements.

## 7. Timeout and cancellation

The existing two timing probes use bounded fixed WAITFOR and require specific
timeout/cancellation SQLSTATE values. Cancellation waits for a server-observed
checkpoint when the required observer permission is separately approved. They
exercise raw driver behavior, not every SDK-scope failure boundary. Neither ran;
native timeout/cancel classifications and latency remain unverified.

## 8. Resource cleanup and pooling

Offline tests cover attempted cursor closure, rollback/close, poisoned scopes,
last-report preservation and publication failure. No native cursor, transaction
termination, session disappearance, fixture cleanup or cleanup latency was
observed. The existing optional session observer requires actual DMV visibility;
client object closure alone cannot certify server cleanup.

The integration process disables pooling. Production pooling/reset is outside
that evidence and remains unverified. No fixture was created, so Phase 12 has no
fixture cleanup action or residual fixture to claim as a measured cleanup result.

## 9. Security and compatibility

Host identity, catalogs, physical mappings, row policies and execution opt-in retain
their contracts. Current authorization remains independent of database snapshots.
No model SQL, production row transmission, browser-provided infrastructure,
permission expansion, automatic database retry or new dependency was introduced.
The explicitly authorized SQL settings were used only for the failed connection.
Credentials were not logged; model configuration was not used. The `.env` file
remains byte-identical. No existing integration opt-in was enabled.

## 10. Implementation changes

Changes are limited to this report, versioned evidence, roadmap and current SDK
testing/consistency/release guidance. All SDK modules, compiler/provider/session
contracts and existing test infrastructure retain their starting bytes. No native
defect could be reproduced without a native run, so no production correction or
additional mock-test layer was justified.

## 11. Regression verification

The original Phase 12 starting full suite and thirteen existing approval tests pass. The twelve
native cases skip for missing authorization; the older optional native case also
remains skipped in ordinary offline runs. After documentation changes, the existing
release helper reran full pytest, the fourteen-schedule SQLite probe, dependency
checks and all historical semantic gates. Actual Windows Python 3.10 and Ubuntu
WSL2 Python 3.12 installed-package environments are checked against the unchanged
45-module SDK digest. Final results, exact versions, timings and commands live in
the versioned record and `dist/phase12/final-verification.json`.

Those full three-runtime runs belong to the preserved v1 record and unchanged SDK
source; they are not new native observations or reruns of this follow-up. Current
follow-up approval/gating, documentation/package checks and preservation evidence
are recorded separately in v2 and
`dist/phase12-production-readonly/attempt-01/final-verification.json`.

Original D02/D03 remain expected historical Phase 03 outcomes. Original invalid
Phase 08 author scripts remain distinguishable from corrected scripts. Existing
evaluations are not rescored by changing expected data. Package inventories and
installed-wheel smoke checks retain their separate, bounded claims.

## 12. Release-readiness assessment

| Capability | Phase 12 classification |
|---|---|
| Existing approval gate / disabled suite collection | Verified offline |
| SDK compilation, authorization, sessions and SQLite snapshots | Offline regression evidence |
| Production read-only connection | One authorized attempt failed, SQLSTATE 08001 |
| Native SQL execution / type mapping | Blocked; zero SQL statements |
| Read-only principal / server isolation metadata | Not obtained |
| Native SNAPSHOT / concurrent writer behavior | Blocked; not executed |
| Native timeout / cancellation | Blocked; not executed |
| Server transaction/session cleanup | Unverified |
| Production pooling reset | Unverified; excluded from prepared nonpooled claim |
| Production workload/resource limits | Unverified |
| Hosted CI / live-model generalization | Not executed |

No Level B native verification or Level C production reliability is claimed.

## 13. Remaining risks and resource implications

All native gaps above remain. Stronger snapshots hold connections and may retain
versions longer; production lock/version-store pressure, connection lifetime and
cancellation/cleanup latency have no Phase 12 measurement. Offline test durations
are test-run timings, not database throughput or production performance evidence.
Compatibility mode can still mix states; snapshot mode requires explicit host use
and eligible sources. A database snapshot does not make authorization and a
separate session store an atomic distributed transaction.

## 14. Next priority; Phase 13 not started

Resolve the connection failure securely before another separately initiated
production assessment. Read-only access must be independently established before
source queries; short limits and certificate validation remain mandatory. No
retry or TLS/permission relaxation is authorized by the failed attempt.

For full Phase 12 verification, obtain isolated-environment authorization and
execute the existing suite before a separate operational-hardening phase. Require observed
native versions/encryption, independently correct types/results, coherent snapshot
versus compatibility schedules, transparent unsupported capability, bounded
timeout/cancel, observed cleanup at the approved level and no residual fixtures.
Close identified coverage gaps in the same existing suite under that approved
scope. If later called Phase 13, prioritize native execution and then production
pool reset/operational hardening; do not repeat preflight-framework preparation.

## 15. Git status and proposed commit

Branch/revision/index are unchanged. Prior source/tests/evaluations/ignored
evidence remain preserved. The verification record lists the five intentional
documentation updates separately from new Phase 12 files. No commit, push,
publication or deployment occurred. One authorized connection attempt failed;
no SQL statement, business read or database modification occurred.

Proposed commit message: `docs: record authorized read-only SQL Server connection failure`.
