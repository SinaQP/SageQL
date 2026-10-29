# Phase 10 — runtime compatibility and release engineering

2026-10-27. Scope and non-goals: [Phase 10 plan](PHASE10_PLAN.md).
Repeatable commands: [installation/release guide](SDK_RELEASE.md). Measured
environment/command records: [matrix v2](../evaluations/compatibility/phase10.v2.json).
Raw logs, first attempts, archives and final artifact sidecars remain under the
ignored `dist/phase10/` directory. No Phase 11 work, commit, push or publication.

## 1. Executive assessment

Actual CPython execution closes the earlier minimum-runtime gap. The unchanged
SDK passes its 2,119-test baseline on six Windows Python versions, including
3.10.22 with exact core lower bounds. Ubuntu/WSL2 3.12.3 passes the baseline plus
six then-existing release tests. Wheel, sdist, editable and optional-extra
installations work in clean environments. Every installed SDK module and both
independent-host examples run with checkout imports excluded.

Public PyPI SDK resolution is **blocked by observed network/DNS failures** in this
session. This is separate from successful offline dependency resolution and
initial public-index tooling provisioning. Offline installs use cached original
wheel archives and explicitly identified upstream source builds, never copies of
installed packages. Hosted CI, native non-WSL Linux deployment, real SQL Server,
live-model behavior and multi-read snapshots remain unverified. No SDK source or
dependency-range correction was necessary.

## 2. Verified starting baseline and preservation

Branch `main`, HEAD `b74c10974265dcac522b3e23623e0f4f9a8ae582`; empty index,
17 tracked modifications and 197 untracked files from Phases 01–09. Before new
edits, all 327 nonignored repository files were copied with SHA-256 hashes to
`dist/phase10/starting/tree` and `starting/state.json`. Initial full pytest:
**2,119 passed, one opt-in SQL Server skip**, 80.76 seconds, exit 0.

All measured installed packages bind to the unchanged package Python-source
digest `74ee880e1af76afc317501b51528beba663a42c674895dfc3f146b20c4925fe1`:
sorted package-relative `.py` paths followed by their raw bytes. This is the same
binding used by the evaluation configuration. The starting snapshot additionally
records a different, explicitly named per-file-hash ledger digest; those two
algorithms must not be confused.

Only additive release assets and README/SDK/roadmap integration are intended.
Earlier SDK code, tests, frozen corpora, references, reports, measurements,
disabled live packets and original/corrected Phase 08 evidence retain their
bytes. Ignored private configuration and Rahtal reporting output were not read
or modified. Prior source changes remain uncommitted.

## 3. Actual Python runtime matrix

| Runtime / platform | Core dependencies | Full pytest | Seconds |
|---|---|---:|---:|
| CPython 3.10.22 / Windows | sqlglot 26.0.0, dotenv 1.2.0 | 2,119 pass / 1 skip | 151.90 |
| CPython 3.11.0 / Windows | sqlglot 30.15.0, dotenv 1.2.2 | 2,119 / 1 | 80.09 |
| CPython 3.12.0 / Windows, extras | same representative core | 2,119 / 1 | 77.84 |
| CPython 3.13.14 / Windows | same representative core | 2,119 / 1 | 108.47 |
| CPython 3.14.10 / Windows | same representative core | 2,119 / 1 | 122.75 |
| CPython 3.15.2 / Windows | same representative core | 2,119 / 1 | 132.61 |
| CPython 3.12.3 / Ubuntu WSL2 | same representative core | 2,125 / 1 | 137.73 |

The Linux total includes the first six release-tool tests added during this phase;
it does not represent additional reporting scenarios. Final release-tool tests
are separately executed across the matrix. Timings include concurrent work and
filesystem differences and are not performance improvement claims.

3.11/3.12/3.13 were already installed. 3.10/3.14/3.15 were downloaded into an
ignored task-local directory using uv 0.13.6 with `--no-bin --no-registry`.
No system interpreter/default/PATH change was made. uv uses
[Astral's standalone Python builds](https://docs.astral.sh/uv/concepts/python-versions/),
not Python.org Windows installers. [Python.org identifies the 3.15 release](https://www.python.org/downloads/release/python-3150/).
Exact interpreter, SQLite and platform versions are retained in the matrix.
This evidence does not certify future releases, every patch, free-threaded
builds, PyPy, ARM, macOS or Linux Python versions other than the measured 3.12.3.

## 4. Dependencies and isolation

The declarations remain `sqlglot>=26,<31`, `python-dotenv>=1.2,<2`,
`openai>=1.99,<3`, `pyodbc>=5.2,<6`, `pytest>=8,<10`, `build>=1,<2`, with build
backend `hatchling>=1.26`. No runtime dependency, pin or supported-Python change.

The boundary matrix deliberately avoids a Cartesian product. Python 3.10 covers
the exact core floor; representative newer runtimes cover cached 30.x/1.2.x
versions, and the original development environment also exercises sqlglot
30.19.0 / dotenv 1.2.3. Python 3.12 covers both OpenAI 1.99.0 + pyodbc 5.2.0 and
OpenAI 2.53.0 + pyodbc 5.3.0. The lower optional environment also runs pytest
8.0.0 and build 1.0.0; 397 focused adapter/session/provider/intent/continuation
tests pass with one SQL Server skip, followed by strict 61-case evaluation.
Current optional extras run the full baseline. Real OpenAI client construction
uses a fixed synthetic unused key/invalid endpoint with socket connections
blocked; pyodbc imports its actual native extension. No request/connection occurs.

Before test tooling installation, core-only environments prove OpenAI, pyodbc,
pytest and build absent while importing all 44 package modules and running both
independent-host examples. SQLite reporting, persistence and SQL compilation are
covered by the full/focused suites. Optional native extras on other Python/OS
combinations remain unexecuted; importing pyodbc on Windows does not certify a
Linux driver manager or an actual SQL Server driver.

PyPI requests to the explicit public index failed through timeouts or
`files.pythonhosted.org` name resolution. "No matching distribution" at the end
of these failed requests is not evidence of an incompatible version. Cached wheel
archives were recovered by distribution metadata and hashed. Missing lower-bound
libraries were built from official upstream tags: sqlglot v26.0.0, python-dotenv
v1.2.0, OpenAI v1.99.0, build 1.0.0 and Hatchling 1.26.0. Their commits and
artifact hashes are recorded. These local builds are not claims about the bytes
of published wheels. Additional tool-only source builds supply missing bootstrap
dependencies; see the matrix's provenance notes.

## 5. Packaging and installation

Metadata remains SageQL 0.1.0, MIT, Python >=3.10, entry point
`sageql = sageql.cli:main`, and the same core/optional requirements. All 44
runtime modules are present and byte-bound to current source. Examples/evaluation
tooling are intentionally outside the wheel and supplied by the sdist/checkout.

Initial wheel and sdist builds succeed with Hatchling 1.32.4 / build 1.6.1.
Actual Python 3.10 also builds both artifacts with the exact lower build tools,
Hatchling 1.26.0 / build 1.0.0. The archive gate accepts semantically equivalent
marker quote styles from both backend generations. A stale archive correctly
fails comparison when its bundled release helper differs from subsequently
edited source; final inventory must be run against the frozen build inputs.

Clean standard-wheel installs work on every measured runtime; a separate source
distribution installation and an editable installation on 3.12 both pass imports,
examples, 397 focused tests / one skip, pip check and strict evaluation. The first
editable attempt lacked the offline `editables` helper. Supplying its cached wheel
allows an ordinary isolated backend install; no SageQL packaging change is needed.

Final archive inventories, hashes, byte sizes, installation-origin checks and
defined reproducibility measurements are saved separately in
`dist/phase10/final-v2/verification.json`. That ignored sidecar avoids embedding an
artifact's own hash recursively inside its sdist. The versioned compatibility
matrix binds earlier measured package artifacts to the identical SDK source.

## 6. Windows/Linux and persistence

Ubuntu actually executes under WSL2, kernel 6.6.87.2, glibc 2.39, CPython 3.12.3,
SQLite 3.45.1. The installed virtual environment resides on the mounted workspace;
pytest synthetic session databases use Linux temporary paths. Both in-memory and
SQLite session implementations retain their existing ownership, replay, atomic
publication, revision, rollback, catalog and current-access tests. POSIX evaluation
locking and atomic JSON replacement execute on Linux; Windows exercises msvcrt.
No Linux behavior is inferred from Windows results.

Ubuntu's system Python lacks ensurepip. Task-local uv creates its environment
without apt/admin changes. `/tmp` environments were unavailable on later WSL
invocations, so the retained environment uses ignored workspace storage. WSL
commands use `--exec`: the initial shell-based invocation interpreted `<` in a
version constraint as redirection. This was a command-wrapper issue, not an SDK
path or dependency bug. Native Linux hosting/container behavior remains untested.

An early tool execution was interrupted; newly created logs/checkpoints contained
invalid bytes. All 327 starting-file hashes were rechecked and unchanged. The
attempt remains under `dist/phase10/matrix/`; fresh named attempts supply the
reported results. No root-cause claim or database retry follows from that event.
Final semantic/evaluation runs complete without an unexplained failure.

## 7. SQL Server and SQLite boundaries

Full suites exercise parameter binding, typed schemas/results, Decimal/numeric
handling, date/timestamp restrictions, collation-sensitive compilation assumptions,
timeouts, cancellation, rollback/close and fake-driver failure paths. Core-only
imports also establish optional pyodbc isolation. SQLite synthetic end-to-end
reports and both persistence stores execute on Windows and Linux.

**Real SQL Server execution remains unverified.** No connection configuration was
read, no driver/database connection was attempted and no database object or
business data was changed. One existing synthetic SQL Server test remains skipped
unless its separately approved host opt-in is supplied. Actual driver/server
type, collation, cancellation and workload behavior require that separate test.

## 8. CI and release controls

The remote is GitHub; no earlier CI workflow was present. The new
[workflow](../.github/workflows/compatibility.yml) uses commit-pinned checkout,
setup-python and upload-artifact actions, read-only contents permission and
disabled checkout credential persistence. It creates clean environments before
core smoke tests, covers lower/current/optional samples, all offline cohorts,
Windows/Linux Python versions and source/editable installation. Archive privacy,
metadata and source bindings are mandatory. Only public synthetic logs/artifacts
are uploaded. No secrets, live models, real SQL Server, deployments or publishing.

Remote action tag tips were resolved before pinning. actionlint 1.7.12, obtained
from its official GitHub release and checked against the release API SHA-256,
validates the workflow with exit 0. Actual equivalent Python/package/evaluation
commands execute locally. Hosted GitHub Actions orchestration, runner images,
cache restore and artifact upload remain **not executed**, rather than claimed
green. CI will need a normal authorized commit/push before it can provide evidence.

## 9. Confirmed defects and fixes

No SageQL production-code/runtime incompatibility was found. Focused corrections
are limited to the new release tooling:

- Older Hatchling emits single-quoted extra markers; the first metadata gate
  falsely rejected equivalent requirements. A failing regression precedes quote
  normalization; altered dependency ranges still fail closed.
- Phase 06 defaults to the assessment subset (26 cases). The new gate initially
  inherited that default. A focused failing command-contract test precedes
  explicitly selecting all cohorts; 45/45 runs are then measured on both platforms.
- A test double replaced the shared subprocess module and interfered with Python
  3.10's platform detection. It now replaces only the release module's subprocess
  binding. Actual SDK behavior was unaffected.

Nine focused release tests cover valid/altered/missing module inventories,
private paths, archive links, dependency metadata, equivalent old marker syntax
and the offline gate's cohort/authorization contract. Final Git/archive review
found an empty root file left by WSL shell redirection. Its first archives are
retained, the task-created file is removed, and a new guard rejects unexpected
sdist roots. Matrix v1/first artifact sidecar retain that initial measurement;
matrix v2 and final-v2 artifacts supersede them. First failures remain in
ignored logs. Missing offline tools, WSL quoting and public-index failures are
recorded as environmental/tooling limitations, not SDK defects.

## 10. Security and API compatibility

No SDK constructor, provider decoder, catalog contract, permission, specification,
SQL compiler/adapter, session schema, calendar logic or language behavior changes.
Host-owned catalogs/auth/infrastructure remain authoritative. Execution stays
explicit, deterministic, parameterized and read-only; models receive no identities,
row data or credentials. There is no model-written SQL, permission expansion,
new relationship, silent partial report or automatic database retry.

The wheel inventory admits only exact current runtime bytes plus distribution
metadata. Archive checks reject environment/configuration files, ignored output,
databases, traversal and links. The sdist retains public synthetic evidence and
source assets; private reporting/configuration is excluded. Inventory comparison
does not claim exhaustive content-based secret detection or dependency auditing.

## 11. Regression verification

All original full Windows matrix runs: 2,119 passed / one skip. Linux full run:
2,125 / one skip. The final current-tree suite passes **2,128 tests / one skip**,
66.83 seconds, exit 0, after the archive guard. All nine final release-tool tests pass across the
six Windows runtimes and Linux. Output and command statuses are retained in the
matrix/sidecar. Browser regressions pass with bundled Playwright and local
Chrome: tabs, history, failures, cached retries, downloads, mobile layout/modes.
pip check, compileall and git diff --check pass.

On Windows 3.10 lower core and Linux 3.12 representative core:

| Cohort | Measured result | Expected exit |
|---|---:|---:|
| Strict regression | 61/61 | 0 |
| Held-out Phase 03 corpus | 30/30 | 0 |
| Historical complete Phase 03 | 40/42, only D02/D03 | 1 |
| Phase 04 | 26/26 | 0 |
| Phase 05 | 37/37 | 0 |
| Phase 06, explicit all | 45/45; reports 36/36 | 0 |
| Phase 07 | 27/27; reports 24/24 | 0 |
| Phase 08 corrected script | 14/14; reports 16/16 | 0 |
| Phase 09 | 13/13; reports 18/18 | 0 |

Measured complete cohorts retain zero incorrect accepted specifications and
unauthorized reads. Original invalid Phase 08 `refinement` outputs still remain
rejected; the historical original/corrected script matrix is not rewritten.
No new natural-language benchmark or model call was added. Commands, exit codes,
timings, versions, source bindings and classifications are machine-readable.

## 12. Release-readiness classification

| Area | Classification | Evidence/limit |
|---|---|---|
| Minimum CPython / core floor | Verified | Actual 3.10.22 full runtime tests, source-built exact floors |
| Windows 3.11–3.15 | Verified with limitations | Listed patch versions and representative dependencies only |
| Core/optional dependency samples | Verified with limitations | Bounded offline matrix; optional native coverage is Windows 3.12 |
| Fresh public-index SDK resolution | Blocked | Observed PyPI timeout/DNS failures; rerun required |
| Wheel/sdist/editable behavior | Verified with limitations | Clean offline installs; final inventories/sidecar distinguish artifact steps |
| Windows / SQLite / session stores | Verified | Existing full regression contracts |
| Linux | Verified with limitations | Actual Ubuntu WSL2 3.12.3, not native deployment certification |
| SQL Server compiler/fake driver | Verified | Existing full/focused safety suites |
| Actual SQL Server/ODBC driver | Not executed | Separate approved synthetic environment required |
| Live model baseline | Not executed | No authorization; existing disabled packets preserved |
| Multi-read snapshot consistency | Not executed | Existing scoped design/implementation gap |
| CI configuration | Verified with limitations | actionlint/local commands; no hosted run |
| Packaging privacy/reproducibility | Verified with limitations | Defined source inventory/local build procedure; final sidecar records exact bytes |

This is substantial offline release evidence, not unconditional production
readiness or certification of all combinations allowed by open version ranges.

## 13. Remaining risks

Repeat trusted-index SDK dependency resolution when connectivity works, verify
hosted CI, and test any additional native-extra/runtime/deployment combination
before claiming it. An identified cached artifact is not fresh registry
resolution. Local source-built dependency wheels are not upstream published
binary attestations. The early interrupted file-write event's underlying cause
remains unverified. Finite offline semantic tests do not prove live-model quality.
Production ODBC behavior and multi-read consistency remain material release gaps.

## 14. Phase 11 recommendation — not started

Prioritize a separately scoped, explicitly approved **synthetic SQL Server runtime
and multi-read consistency assessment**: actual driver/type/date/collation,
timeouts/cancellation/cleanup and snapshot behavior across report/lookup/name reads.
Specify consistency semantics before adding transaction/retry behavior. Do not
use production credentials or create business objects implicitly. A separately
authorized live-model baseline remains the principal unmeasured semantic-quality
assumption; Phase 10 does not authorize it or require another preparation corpus.

## 15. Git status and proposed commit

Branch and revision are unchanged; index empty. Earlier modifications and
untracked assets remain. New assets are the plan/report/release guide, versioned
matrix, release helper/tests and GitHub workflow; README, SDK guide and roadmap
link the results. Exact final status and preservation hashes are in the matrix
and ignored final sidecar. No reset, clean, rebase, commit, push or publication.

Proposed commit message:
`build: verify Python compatibility and add offline release gates`
