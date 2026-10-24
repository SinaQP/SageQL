# SageQL agent entry point

Before changing code, read [agent-rules/Agent.md](agent-rules/Agent.md). Follow its product contract, working rules, and verification workflow.

Fixed local absolute/percentage changes across two ungrouped aggregate periods
are scoped in [docs/SDK_COMPARISON_CHANGES.md](docs/SDK_COMPARISON_CHANGES.md).
Models select this typed operation; formulas, grouped alignment and result
transmission to models remain unsupported.

The approved embedded SDK in `sageql.sdk` accepts developer-registered tables/views, reporting concepts, infrastructure and trusted per-actor policies; it supports persistent report conversations, deterministic SQL Server compilation/execution and table/chart JSON. Its separate scope and safety design is [docs/SDK_SQL_SERVER.md](docs/SDK_SQL_SERVER.md); operations beyond registered dimensional relationships need another scoped design. Execution requires explicit host opt-in. Never run model-written SQL or accept infrastructure/identity from browser messages.

The registered relationship extension is scoped in [docs/SDK_RELATIONSHIPS.md](docs/SDK_RELATIONSHIPS.md). Hosts may register directed many-to-one equality mappings and dimension/filter imports across existing sources. The compiler applies both sides' policies, rejects duplicate visible source keys, and groups/ranks before limits. Models select exposed business concepts, never join keys or types. Fact-to-fact joins, recursive paths and arbitrary formulas remain outside this extension. Parameterized rolling Gregorian windows resolve locally; aggregate filters apply after grouping.

The explicitly registered entity-name lookup extension is scoped in [docs/SDK_ENTITY_LOOKUPS.md](docs/SDK_ENTITY_LOOKUPS.md). It resolves one full name through a bounded policy-bound source SELECT, then binds its unique identity to the registered target report filter. It permits fixed full-name normalization over declared text columns, not model-selected joins, fuzzy matching or arbitrary expressions. Lookup results and resolved identities never enter model context.

Registered entity-label dimensions are scoped in [docs/SDK_ENTITY_LABELS.md](docs/SDK_ENTITY_LABELS.md). They preserve identity aggregation/ranking and resolve display names afterwards through bounded policy-bound source SELECTs. The host fixes the mapping; models cannot choose relations, sort by resolved labels or receive identities/results. Conflicting labels and truncated source reads fail closed.

The historical flow still includes logical planning, SQLite generation/validation and explicit read-only SQLite execution after discovery. The isolated `sageql_rahtal/` pilot retains its approved daily-performance scope; ignored `local_config.py` holds questions/run options and `.env` holds credentials. Step 5 has not been defined.

The explicitly selected Rahtal frontend uses the SDK with registered existing employee-profile, activity and activity-topic sources, a real configured interpreter, and a fixed local reporting principal protected by a workspace token. Registered dimension-only listings use bounded DISTINCT SELECTs and the same actual source policies. The frontend creates no database objects and does not enable model-selected joins or production employee authorization.

When reporting work, include a commit message based on the actual changes.

The requested employee decline ranking is scoped in [docs/SDK_ENTITY_DECREASES.md](docs/SDK_ENTITY_DECREASES.md): one registered label identity, one additive metric, complete bounded period groups, local absolute-loss ranking before the output limit, then policy-bound names. Candidate truncation fails closed; models never choose formulas or receive identities/results.

Explicit Jalali months are scoped in [docs/SDK_JALALI_MONTHS.md](docs/SDK_JALALI_MONTHS.md). The authorized manager extension in [docs/SDK_MANAGER_REPORTS.md](docs/SDK_MANAGER_REPORTS.md) adds host-defined workload defaults, the fixed activity-topic relation, Persian date-only ranges/years/relative periods and bounded Persian monthly buckets. Models never convert dates; missing years in named months still require clarification. Timestamp conversion and unregistered calendar/formula operations remain outside scope.

The fixed registered sum-per-participant metric is scoped in [docs/SDK_PARTICIPANT_MEANS.md](docs/SDK_PARTICIPANT_MEANS.md). Hosts declare numeric amount and integer/text participant columns in the same physical fact source; models select only the metric concept. It preserves policies, group-before-limit behavior and current-position relationships. Unknown participant identities make the mean unknown. Arbitrary ratios/formulas and historical positions remain outside scope.

The fixed matching-day count is scoped in [docs/SDK_MATCHING_DAY_COUNTS.md](docs/SDK_MATCHING_DAY_COUNTS.md). A typed false-by-default flag adds counts of filtered daily groups per registered entity identity/period before output limits and name enrichment. It requires bounded daily entity tables and preserves ordinary reports. Models never supply window partitions, SQL or formulas; arbitrary windows and computed-count filtering remain outside scope.

Reporting reliability hardening is documented in [docs/REPORTING_RELIABILITY_PHASE3.md](docs/REPORTING_RELIABILITY_PHASE3.md). Bounded user evidence constrains intent and every final provider specification. Unavailable requested operations return transparent unsupported outcomes; the typed requirement ledger cannot register capabilities. Structured repair is opt-in, shared and bounded; no database operation is automatically retried. Safe stage/reason/field diagnostics exclude rejected values, row data and secrets.
