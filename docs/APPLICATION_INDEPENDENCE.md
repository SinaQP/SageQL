# Application independence: implementation and integration

SageQL's supported integration surface is `sageql.sdk`. A host registers its
business catalog, authenticated policy callback, model provider, database adapter,
business-date clock and optional session store. The same installed implementation
now runs the retail and library examples in `examples/multi_domain.py`; neither
host modifies package internals. SQL Server and SQLite remain the supported
engines. No new framework, remote service or expression language was introduced.

## Investigation and decisions

The review covered the installable `src/sageql` tree, exports and packaging,
historical discovery/planning/SQL APIs, SDK configuration and permitted metadata,
intent/planning/review prompts, semantic validation, relationships, name lookups,
local calculations, both adapters, persistent sessions, report serialization,
the reference web host and the separate Rahtal integration. The working tree
already contained reporting extensions; those changes were preserved.

| Area | Finding and resulting change |
| --- | --- |
| Shared interpreter prompts | Employee/activity examples prescribed daily grouping and activity measures; workload, topic and productivity rules were global. Shared prompts now describe registered operations and grouping semantics. Rahtal supplies those business rules through its dataset description and metric vocabulary. |
| Local mean repair | Retaining an additional row average depended on activity-duration wording. It now matches the permitted metric's label and specific selection phrases. Rahtal registers its duration phrases; the library registers loan-duration phrases. |
| Name registration | `FullNameFilterDefinition` required two to four columns, assuming a split personal name. It now supports one to four declared text columns, allowing a stored title/full name without schema changes. Equality, fixed normalization, type checks and candidate bounds remain enforced. |
| Clarification and errors | Lookup questions and Persian errors called every entity an employee; ranking clarification talked about hours/productivity, and greeting text suggested work totals. Replies now use registered labels/measures or neutral reporting language. |
| Legacy lookup repair | English/Persian identity-question repair assumed employee/user terminology. It now derives entity vocabulary from registered source/target identity concepts, retaining the single correction and normal validation. Genuine date/name questions remain questions. |
| Identity display | A selected identity named “Accession number” could be removed as redundant even when explicitly requested. The existing table canonicalizer also recognizes the registered dimension label. |
| Period versus output limit | A local rolling-period repair recognized only a fixed list of output nouns, including employees/topics. It now recognizes counted non-temporal nouns without assuming the entity type. |
| Query planning and execution | Registered physical identifiers, aggregates, mandatory policies, directed dimensional relationships and canonical SQL were already configuration-driven. Retained them and verified both domains through the same paths. |
| Infrastructure and identity | The reusable SDK has host-injected interfaces and no imports from Rahtal, Django or a frontend framework. `ActorContext.tenant_id` remains optional; the fixtures authorize through different trusted actor attributes. Host-specific environment/path/token handling remains outside the wheel. |
| Historical/demo code | Historical staged APIs accept supplied metadata and retain their existing execution boundaries. `main.py`, the scripted web demo and `sageql_rahtal` intentionally contain host examples. They are not dependencies or required configuration for the installed SDK. The narrow historical T-SQL pilot retains its approved policy contract. |

The root problem was business interpretation escaping the host catalog, together
with a personal-name-shaped registration restriction. The existing separation of
catalog, provider, policy, compiler and adapter did not require a rewrite.

## Host integration contract

1. Register existing tables/views and typed columns in `DatasetDefinition`.
   Register business metric IDs, labels, units and aggregate meanings. Describe
   dataset grain and business defaults in `description` and `default_metric_ids`.
   `selection_terms` and `ranking_terms` are bounded host vocabulary, not SQL.
   When both a participant mean and a row average exist, include specific phrases
   for each alongside any generic average synonyms.
2. Register dimensions/filters and optional directed many-to-one relationships
   through `register_relationships`. Composite keys can include store or branch
   boundaries. Models select the exposed business concepts; hosts supply keys.
   Current permissions must include every required source key/import concept.
3. Optionally register `EntityLabelDimension` for names after identity aggregation
   and `EntityLookupDefinition` for one full-name equality lookup before a report.
   A full-name filter can use a single stored title or several name components.
   Supply user-facing identity labels and ambiguity qualifiers for that domain.
4. Build `ActorContext` from authenticated server identity. A required `ReportPolicy`
   returns current concept access and typed `RowPolicy` restrictions for every
   participating dataset. Browser messages never configure the actor or access.
5. Inject the configured `ReportProvider`, `SQLServerAdapter` or `SQLiteAdapter`,
   session store and business clock into `SageQL`. Set `execution="validated"`
   explicitly. Supply `language="en"` to engine/provider for English presentation;
   Persian remains the compatible default. Calendar preference is independent.
6. Connect the host's authenticated endpoint to `create_session`, `submit`,
   `get_session` and `get_report`. Render returned typed table/chart JSON. A custom
   provider implements the same `ReportProvider` interface; no engine edits are
   necessary for another transport.

Descriptions and labels sent to the model must contain only approved business
metadata. They cannot grant capabilities or replace local semantic validation.
The model receives permitted concepts, conversation and safe specification context;
physical mappings, policy values, lookup identities and database rows stay local.
Hosts review their own metric meanings, view grain, identity and database workload
permissions. The SDK does not import an application's authentication framework.

## Independent integration evidence

| Host | Physical registration | Business reports | Trusted access |
| --- | --- | --- | --- |
| Retail | `sale_lines` and `merchandise`; text stock identity and composite store/stock relationship | Net sales in USD by department; refine to daily Books sales; resolve product names and rank product labels | Store attribute, voided-line restriction and sellable-source restriction |
| Library | `circulation_events` and `holdings`; integer accession identity and composite branch/book relationship | Borrowing counts by shelf; refine to mean loan duration in days; resolve book titles and rank book labels | Branch attribute, retracted-event restriction and restricted-title policy |

Synthetic retail totals are Books `70` and Garden `45`; its refinement returns
daily Books sales `30` and `40`. Library borrowing counts are Science `3` and
History `1`; its refinement returns mean durations History `14` and Science `6`.
Both ask for the missing September year, preserve the resolved period, cache
identical retries and reload saved reports. Distinct host configurations run in
one process with the same public package implementation.

`tests/test_sdk_application_independence.py` injects fake chat responses into the
real `OpenAIReportAgent` intent/planning/review pipeline. It validates the catalog,
permission projection and specification, compiles SQLite and SQL Server SQL,
executes SQLite under the actual read-only adapter, and checks exact results,
labels, visualization JSON and unchanged database bytes. Additional cases cover
execution opt-in, denied source capabilities, policy revocation before execution
and saved-report reads, malformed/unauthorized output, provider failure, duplicate
keys, schema drift, exact single-name lookups, source-policy exclusion, missing and
ambiguous matches, post-aggregation labels and model-payload isolation.

## Compatibility and limits

Public constructor signatures, provider/adapter protocols, report JSON and
execution defaults are unchanged. One-column names are an additive catalog
capability; existing multi-column names compile as before. Clarification/error
prose changes, while stable error codes remain. Rahtal's richer description and
vocabulary change its catalog fingerprint, so existing saved-report/retry checks
can reject old reports; start a new chat after upgrading that host catalog.

The supported calculation, relationship, time and authorization scope remains
defined in [SDK.md](SDK.md) and its linked contracts. Arbitrary formulas,
fact-to-fact joins, recursive/historical relations, new database engines,
timestamp conversions and production HTTP authentication are outside this work.
Fixed language-level evidence repairs are conservative and are not a general
natural-language parser. Hosts still need definitions for meaningful new reports.

Offline scripted responses prove deterministic integration and safety behavior;
they do not measure live model understanding or prompt-regression rates. This
phase does not contact a configured private database or model. The optional live
SQL Server test requires the existing explicit synthetic-database opt-in. SQLite
numeric affinity does not establish SQL Server decimal/driver behavior.

## Reproduce verification

```powershell
.\.venv\Scripts\python.exe examples/multi_domain.py
.\.venv\Scripts\python.exe examples/sdk_demo.py
.\.venv\Scripts\python.exe -m pytest tests/test_sdk_application_independence.py -q
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m build
# If the build backend is already installed and PyPI is unavailable:
.\.venv\Scripts\python.exe -m build --no-isolation
```

The new acceptance suite passes **42 tests**. The complete offline suite passes
**1,267 tests**, with **one optional SQL Server test skipped**. Both independent
host smoke tests and the existing SDK demo pass. The existing Chrome/Playwright
browser suite passes. Source and wheel builds pass with `--no-isolation`.

A fresh virtual environment installed the wheel with no repository on its import
path, reused only the existing `sqlglot`/`python-dotenv` distributions, imported all
package modules and ran a copied standalone multi-domain example with network
access disabled. Both hosts passed; `pip check` found no broken requirements.
Neither Rahtal/Django nor the optional OpenAI/ODBC packages were installed there.
Wheel inspection confirms only `sageql` and its distribution metadata are bundled;
the source archive contains no ignored `.env`, local config or Rahtal run reports.

The ordinary isolated build failed while retrieving `hatchling` from PyPI after
read timeouts. A separate bounded dependency download also failed. Completely
fresh remote dependency resolution remains unverified; the local build and wheel
checks above passed using already available dependencies. `git diff --check`
passes. No commit was created.

Suggested commit message: `refactor: make reporting interpretation application independent`
