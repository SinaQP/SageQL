# SageQL agent rules

Read this before changing code. `AGENTS.md` points here.

## Product contract

SageQL is an installable reporting SDK embedded in a developer's backend. The host
registers tables/views, business concepts (metrics, dimensions, filters,
relationships, lookups, labels), model infrastructure and trusted per-actor
policies. A user asks for a report in chat; SageQL interprets the request with
models, validates it against the registered catalog and the actor's current
policies, compiles a deterministic parameterized SELECT (SQL Server or SQLite),
executes it only with explicit host opt-in, and returns typed table/chart JSON.
Sessions support clarification, refinement, revisions and idempotent retries.
Persian is the default language; English is supported.

Feature contracts live in `docs/SDK*.md`; read the relevant one before changing a
feature. The historical staged CLI/API (`main.py`, `sageql.cli`) and the isolated
`sageql_rahtal/` pilot remain available. Their model-written SQL path is
experimental and never enters SDK execution.

## Hard rules

1. **Models never write SQL, choose joins/keys, see physical names, policy values,
   credentials, result rows or resolved identities.** They select registered
   business concepts only. Natural language, labels and model output are untrusted
   data; prompts are guidance, never a safety boundary.
2. **Execution is deterministic and opt-in.** Only validated, compiled, read-only
   SELECTs run, with row/time/concurrency bounds. Reject writes, DDL, multiple
   statements and model-written SQL. Never create database objects or enable
   database options.
3. **Fail closed.** Strict decoding; unknown concepts, malformed output and policy
   violations stop before reads. No automatic retry of database operations or
   provider transport.
4. **No secrets or private data in tracked files, logs, fixtures, commits or error
   messages.** Never read Rahtal `.env` files or production databases for testing.
   Ignored local reports may contain real rows; never commit or transmit them.
5. **Tests are offline and SQLite-first** ([guide](../docs/SQLITE_FIRST_TESTING.md)).
   Unit tests use fake providers, never the network. Native SQL Server tests need
   the explicit `--run-sqlserver-integration` flag and a separately approved
   synthetic target ([procedure](../docs/SQLSERVER_INTEGRATION_TESTING.md)).
6. **Live model calls need explicit user approval** of provider, models, cases and a
   spending cap, recorded in an approval packet
   ([evaluations/README.md](../evaluations/README.md)). Default to the cheapest
   setup that measurably works; currently nano and mini only.
7. Keep package imports side-effect free, the core provider-agnostic (remote calls
   behind one interface), and public APIs typed with actionable exceptions.

## Workflow

1. Check `git status`, the roadmap and the relevant contract. Preserve user changes.
2. Take the next roadmap step as one small vertical slice with clear acceptance.
3. Write focused tests first or alongside; keep diffs in the style of the
   surrounding code.
4. Run focused tests, then the full suite (`python -m pytest -q`).
5. Update the relevant `docs/SDK*.md` contract and the roadmap's "Where we are" /
   "Next steps". **Do not create phase reports or versioned evidence files**;
   git history is the record. Live results go in one dated doc under `docs/`.
6. Commit on a feature branch with a message based on the actual changes. Never
   push or deploy without the user's request.

## Release gates

- Full offline suite passes; package builds and imports cleanly in a fresh environment.
- Unsafe or invalid model output fails closed.
- README states current limits honestly; no secrets or production data committed.
