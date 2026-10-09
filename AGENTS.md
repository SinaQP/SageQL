# SageQL agent entry point

Before changing code, read [agent-rules/Agent.md](agent-rules/Agent.md). Follow its product contract, working rules, and verification workflow.

The approved embedded SDK in `sageql.sdk` accepts developer-registered tables/views, reporting concepts, infrastructure and trusted per-actor policies; it supports persistent report conversations, deterministic SQL Server compilation/execution and table/chart JSON. Its separate scope and safety design is [docs/SDK_SQL_SERVER.md](docs/SDK_SQL_SERVER.md); operations beyond registered dimensional relationships need another scoped design. Execution requires explicit host opt-in. Never run model-written SQL or accept infrastructure/identity from browser messages.

The registered relationship extension is scoped in [docs/SDK_RELATIONSHIPS.md](docs/SDK_RELATIONSHIPS.md). Hosts may register directed many-to-one equality mappings and dimension/filter imports across existing sources. The compiler applies both sides' policies, rejects duplicate visible source keys, and groups/ranks before limits. Models select exposed business concepts, never join keys or types. Fact-to-fact joins, recursive paths and arbitrary formulas remain outside this extension. Parameterized rolling Gregorian windows resolve locally; aggregate filters apply after grouping.

The explicitly registered entity-name lookup extension is scoped in [docs/SDK_ENTITY_LOOKUPS.md](docs/SDK_ENTITY_LOOKUPS.md). It resolves one full name through a bounded policy-bound source SELECT, then binds its unique identity to the registered target report filter. It permits fixed full-name normalization over declared text columns, not model-selected joins, fuzzy matching or arbitrary expressions. Lookup results and resolved identities never enter model context.

Registered entity-label dimensions are scoped in [docs/SDK_ENTITY_LABELS.md](docs/SDK_ENTITY_LABELS.md). They preserve identity aggregation/ranking and resolve display names afterwards through bounded policy-bound source SELECTs. The host fixes the mapping; models cannot choose relations, sort by resolved labels or receive identities/results. Conflicting labels and truncated source reads fail closed.

The historical flow still includes logical planning, SQLite generation/validation and explicit read-only SQLite execution after discovery. The isolated `sageql_rahtal/` pilot retains its approved daily-performance scope; ignored `local_config.py` holds questions/run options and `.env` holds credentials. Step 5 has not been defined.

The explicitly selected Rahtal frontend uses the SDK with approved existing employee-profile and activity sources, a real configured interpreter, and a fixed local reporting principal protected by a workspace token. Registered dimension-only listings use bounded DISTINCT SELECTs and the same mandatory policies. The frontend creates no database objects and does not enable model-selected joins or production employee authorization.

When reporting work, include a commit message based on the actual changes.

Explicit Jalali month selections are scoped in [docs/SDK_JALALI_MONTHS.md](docs/SDK_JALALI_MONTHS.md). The SDK resolves a declared month and year locally to Gregorian date-only bounds. Models never convert dates; missing years still require clarification. Jalali time buckets, relative Jalali periods and timestamp conversion remain outside this extension.
