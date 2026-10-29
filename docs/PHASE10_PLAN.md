# Phase 10 compatibility slice

Establish runtime and installation evidence for the existing SDK without changing
report semantics, host authorization, provider protocols or execution scope.
Preserve all earlier source/evaluation bytes and the original Phase 08 script
distinction. No live models, real SQL Server, production data, publication,
commit or Phase 11 work is authorized by this slice.

Starting tree: main, b74c10974265dcac522b3e23623e0f4f9a8ae582; 17 modified
tracked files, 197 untracked files, empty index. The 327 nonignored repository
files and their hashes were copied to ignored dist/phase10/starting before edits.

Acceptance: actual Python 3.10; representative 3.11–3.13; practical additional
stable runtimes; independently resolved PyPI core lower/current bounds; optional
OpenAI/ODBC isolation; wheel/sdist/editable installs; every installed module and
independent examples outside checkout; full offline regressions, session stores,
SQLite and fake SQL Server gates; actual Linux when available; inspected archives;
repeatable CI without secrets or publication; evidence-based release report.

Use a boundary matrix rather than a Cartesian product. Python 3.10 exercises
sqlglot 26.0.0 / python-dotenv 1.2.0 and optional lower bounds. Representative
newer runtimes resolve current permitted versions. A separate environment covers
current extras, and source/editable installation use representative interpreters.
Fresh installation records must identify runtime, resolved versions, commands,
exit status, elapsed time, artifact hashes and import origin. Current resolution
is a dated observation, not a lockfile or certification of all allowed versions.

Each production fix requires a reproduced compatibility failure and regression.
Tooling changes may add release gates but must not weaken historical scoring or
automatically retry database operations. Classify unavailable infrastructure
separately from source failures. No advertised range changes to obtain green.
