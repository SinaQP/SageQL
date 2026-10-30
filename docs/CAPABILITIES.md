# SageQL capabilities

The detailed feature description previously at the top of the README. The
[README](../README.md) has the short overview.

SageQL is a Python SDK that a developer embeds in their backend to let authorized users create and refine reports through chat. The host registers SQL Server tables or trusted reporting views, approved metrics/dimensions/filters, model infrastructure, and per-user access policies. SageQL interprets a report specification, validates it, generates parameterized SQL itself, and returns a typed table/chart payload for your frontend.

The new `sageql.sdk` API includes persistent conversations, clarification, report refinement, revision checks and idempotent retries. SQL Server is the production adapter target; SQLite supplies an offline reference. The [embedding guide](SDK.md) documents installation, configuration, the JSON contract and limits. The [architecture](ARCHITECTURE.md) records the broader design. The existing staged CLI/API and Rahtal real-data pilot remain available.

Live reference hosts use `OpenAIReportAgent`: independent intent extraction fixes
the effective measures/grouping, a planner proposes a report, a reviewer checks
its meaning, and bounded
feedback can revise the plan or clarification. Registered vocabulary checks
locally preserve explicit business measures and supported period selections;
the shared agents still plan and review reports. Register another catalog to
reuse the same pipeline.
Local checks reject unavailable cross-source combinations, silent grouping changes
and repeated structured clarification after an answer. Intent extraction remains
model-dependent. Authorization, lookup uniqueness and parameterized SQL execution remain enforced
by the SDK. See the [agent contract](SDK_AGENTS.md) for configuration, call
budgets, limitations and custom backends.

The [registered relationship extension](SDK_RELATIONSHIPS.md) supports
management reports across host-defined dimensional sources: multiple measures,
multiple related groupings/filters, aggregate thresholds, period comparisons and
rankings after complete aggregation. The same pipeline works with employee,
customer, product or organizational catalogs. Models never invent join keys;
duplicate dimension keys fail closed. Rolling date windows such as the last
three months resolve locally. Rahtal exposes current job position on activity
reports through this general registration API.

The fixed [participant-mean metric](SDK_PARTICIPANT_MEANS.md) supports a
registered amount divided by distinct participating identities in the same group.
For example, Rahtal uses it for average recorded hours per participating employee,
while ordinary average activity duration keeps its own meaning.
Only trusted hosts register the source columns; models choose the business ID.

[Matching-day counts](SDK_MATCHING_DAY_COUNTS.md) can accompany daily entity
reports: group registered measures, apply typed aggregate conditions, count the
remaining days per identity/period, then sort/limit and resolve names. Thresholds
and periods remain report inputs. The additive flag defaults to false, preserving
organization totals, comparisons, rankings and per-participant means.

Persian is the default conversation and report presentation language. The
reference frontend uses RTL, Persian labels and display digits. Ask naturally,
for example «نام کارکنان را نشان بده» or «ساعات فعالیت روزانه در سپتامبر ۲۰۲۶».
English input remains supported; hosts can explicitly select English output.
Register Persian business labels for your own datasets; see the
[language contract](SDK.md#persian-by-default). Dates still use the approved
Gregorian storage and grouping. The [explicit Jalali month extension](SDK_JALALI_MONTHS.md)
accepts a Persian month and year and resolves date bounds locally; broader Solar
Hijri grouping and timestamp conversion remain outside its scope.
