# Installation and release checks

The current [SQLite-first workflow](SQLITE_FIRST_TESTING.md) makes ordinary
pytest/CI/evaluations independent of SQL Server and production credentials.
Native tests now require the explicit `--run-sqlserver-integration` command flag
as well as their existing separate synthetic authorization. Compiler and mocked
adapter tests stay in the ordinary offline suite; production adapters are unchanged.

## Phase 12 native release readiness

[Phase 12](PHASE12_ENGINEERING.md) remains **Level A: Native verification blocked**.
A later explicit authorization permitted a limited production read-only attempt.
It failed with SQLSTATE 08001 before any SQL; the `.env` file was unchanged and
no retry or certificate-validation bypass occurred. The existing fixture-suite
approval gate remains disabled; no source rows or native type results were obtained.

| Release property | Status |
|---|---|
| Approval rejection and ordinary offline regressions | Verified offline; versioned Phase 12 evidence |
| Production read-only connection attempt | Failed before SQL, 08001; independent read-only enforcement not assessed |
| Native driver/types and SNAPSHOT schedules | Blocked; not executed |
| Native timeout/cancellation | Blocked; not executed |
| Server transaction/session cleanup | Unverified |
| Production pool reset | Unverified; prepared suite disables pooling |
| Production workload | Unverified |
| Live model on synthetic SQLite | Limited P01/P02 verification in [Phase 13](PHASE13_ENGINEERING.md); broader reliability unverified |

Reuse the [existing synthetic procedure](PHASE11_SQLSERVER_TESTING.md) only after
scoped environment approval. Twelve skipped cases are not twelve native passes,
and an eventual green twelve-case run alone does not close all Phase 12 coverage
gaps. Phase 13's synthetic live pilot does not establish native guarantees.
Historical Phase 10/11 measurements below retain
their source/version scope; documentation changes do not certify new native behavior.

## Existing installation and verification procedure

Phase 11 adds [explicit report read consistency](SDK_READ_CONSISTENCY.md) and
always-on offline SQLite scope probes. Its changed SDK is separately verified
on Windows 3.10/3.12 and Ubuntu WSL2 3.12; the Phase 10 matrix below remains the
historical source-versioned compatibility record. See [Phase 11 results](PHASE11_ENGINEERING.md)
and the separately gated SQL Server procedure; no real server test is enabled
by ordinary release checks.

SageQL 0.1.0 declares CPython-compatible Python `>=3.10`. Phase 10 actually ran
CPython 3.10.22, 3.11.0, 3.12.0, 3.13.14, 3.14.10 and 3.15.2 on Windows, plus
3.12.3 on Ubuntu under WSL2. This finite matrix cannot certify future Python
versions, every patch release, other implementations, native Linux deployments
or every possible dependency combination. See [the evidence](PHASE10_ENGINEERING.md)
and [versioned matrix](../evaluations/compatibility/phase10.v2.json).

## Install into a clean environment

Use the checked-out source or a reviewed local distribution artifact. These
instructions do not assert that this repository's package has been published to
PyPI. Core installation requires only `sqlglot>=26,<31` and
`python-dotenv>=1.2,<2`.

```sh
python -m venv .venv
# Linux/macOS: .venv/bin/python; Windows: .venv/Scripts/python.exe
.venv/bin/python -m pip install .
# Or a reviewed wheel / source distribution:
.venv/bin/python -m pip install dist/packages/sageql-0.1.0-py3-none-any.whl
.venv/bin/python -m pip install dist/packages/sageql-0.1.0.tar.gz
```

Select extras only in the host that needs them:

```sh
python -m pip install '.[openai]'       # openai>=1.99,<3
python -m pip install '.[odbc]'         # pyodbc>=5.2,<6
python -m pip install -e '.[dev]'       # pytest>=8,<10; build>=1,<2
python -m pip check
```

Editable installs expose the source checkout and require its continued presence.
Hatchling supplies the `editables` build helper automatically; it is not a new
SageQL runtime dependency. A source distribution builds a wheel with the declared
`hatchling>=1.26` backend. SQL Server also needs a compatible host ODBC driver,
registered sources/policies and explicit execution opt-in. Installing pyodbc does
not establish driver, database, collation or cancellation compatibility.
Real SQL Server execution remains unverified.

Base imports perform no remote calls and do not require OpenAI, pyodbc, pytest
or build. Hosts continue to configure infrastructure, identity and policies in
trusted backend code. Model-written SQL and browser-provided connection/identity
fields cannot enter execution.

## Repeat the boundary checks

The default workflow uses public PyPI with isolated pip configuration. No API key,
production database, live evaluation or publication is part of it. For a lower
core boundary, install the reviewed SDK artifact with `sqlglot==26.0.0` and
`python-dotenv==1.2.0` into an actual Python 3.10 environment. A representative
optional lower boundary uses OpenAI 1.99.0, pyodbc 5.2.0, pytest 8.0.0 and build
1.0.0; native wheel availability depends on the interpreter/platform.

Phase 10 public-index requests timed out or failed DNS resolution after initial
tool provisioning. Measured SDK installs therefore resolved against an explicitly
identified wheelhouse: cached original wheel archives plus documented upstream
tag builds, never copies of installed site-packages. Lower-bound source builds
are not certification of the corresponding published PyPI artifacts. Repeat
public-index SDK resolution in a network-enabled release environment.

Run the following with the chosen environment's Python. Use a new output path
for every attempt. Keep the repository available for tests/examples/evaluation
assets; the installed package must supply SDK imports.

```sh
python -I tools/release_check.py smoke --source . --core-only --output dist/check/core.json
# After installing testing extras:
python tools/release_check.py offline --source . --output dist/check/gates/results.json
# Or reuse a separately recorded full pytest run, and run only evaluation CLIs:
python tools/release_check.py evaluations --source . --output dist/check/evaluations/results.json
# For actual optional imports/client construction, without dispatch:
python -I tools/release_check.py smoke --source . --extras --output dist/check/extras.json
```

`smoke` asserts the import location is inside the active installed environment,
imports every module, blocks socket connections and runs both independent-host
examples. Run from an external temporary directory with absolute script/source
paths to additionally check working-directory isolation. Use `--editable` only
for the intentional editable-install smoke; its import origin is the checkout.
Core-only smoke must precede installing test/build extras.

`offline` disables inherited synthetic SQL Server/evaluation opt-ins, runs the
full pytest suite with pytest's `pythonpath` override cleared, checks installed
dependencies and runs all existing offline cohorts. It explicitly selects
`--cohort all` for Phases 06–09. Historical Phase 03 must exit **1**, with exactly
**D02/D03** failing; any different failure stops the gate. The underlying historical
command remains nonzero. All other commands must exit zero. No database operation
is automatically retried. The helpers refuse an existing output record and
require assertions enabled.

## Build and inspect

```sh
python -m pip install 'build>=1,<2'
python -m build --outdir dist/packages
python tools/release_check.py archives --source . \
  --wheel dist/packages/sageql-0.1.0-py3-none-any.whl \
  --sdist dist/packages/sageql-0.1.0.tar.gz --output dist/check/inventory.json
```

On PowerShell, put the archive command on one line or use PowerShell continuation
syntax. The archive gate checks exact runtime bytes, declared dependency metadata,
entry point, license, required source assets, unexpected archive roots and
unsafe/private file paths. The
wheel contains only runtime modules and distribution metadata; examples, tests,
documentation and frozen synthetic evaluations belong to the sdist/checkout.
Ignored `.env`, local configuration, private reporting output, environments,
temporary databases and build directories must never enter either archive.
This inventory check does not establish universal secret detection.

For reproducibility, hold source bytes, Python, build frontend/backend and
dependencies fixed; set `SOURCE_DATE_EPOCH=1735689600` and build twice into fresh
directories. Compare SHA-256 for both artifacts. Successful construction, valid
inventory, clean installation, index resolution and equal artifact bytes are
separate release properties. Do not promote a single local comparison into a
cross-platform or cross-toolchain reproducibility claim.

## CI and release limits

[GitHub Actions](../.github/workflows/compatibility.yml) defines pinned actions,
read-only repository permissions, clean runtime environments, lower/current
dependency samples, Windows/Linux tests, all offline cohorts and wheel/sdist/
editable checks. Only synthetic evidence/package artifacts are uploaded. There
is no publishing/deployment step or secret requirement. Hosted execution has not
been run in Phase 10. Local actionlint validation and equivalent local commands
are recorded separately from hosted runner results.

Real SQL Server, live-model generalization, multi-read database snapshot
consistency and native non-WSL Linux rollout remain separate release decisions.
The existing disabled live packets and synthetic SQL Server opt-in procedure
retain their explicit authorization requirements.
