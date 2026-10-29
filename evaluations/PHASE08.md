# Phase 08 — focused real-model preflight

**Phase 08 live-evaluation preflight ready; external execution awaiting explicit authorization.**
Completion level A only. No real-model accuracy, usage, cost or latency exists.
The Phase 08 brief explicitly excludes external/billable requests from its general
authorization. Credentials and configured endpoints do not grant permission.

## Frozen selection and independent answers

The v2 selection has **14 trajectories / 23 turns / 16 required reports**, over
retail, library and workshop. P01/P02 form a two-scenario technical pilot; A01–A12
are the remaining assessment. Initial business questions are new relative to the
earlier frozen corpora; generic clarification answers can recur. These are locally
authored, independently calculated and reviewed against existing contracts, not
externally administered blind assessments. All had offline contract exposure;
none had live exposure or supplied a targeted production change. See
`phase08/exposure.v1.json`. Old development, regressions and protocol faults remain
separate and are not presented as fresh natural-model trials.

`phase08/cases.v2.json` contains user turns and local control metadata;
`expectations.v2.json` contains answer keys, complete target specs, independent
rows/types/order/bounds/presentation and exclusions. The loader merges them only
locally into the existing runner shape. Neither file is sent wholesale to a model.
The public SDK builds its usual bounded permitted context from user messages and
trusted registrations; answer keys and results never enter that context.

| IDs | Coverage |
| --- | --- |
| P01 / P02 | Single metric, exact labels, date, grouping, mandatory policies |
| A01 / A02 | Persian/English aliases, related Shelf filter/group, multiple metrics, exclusion, top-N |
| A03 / A04 | Owner/year clarification, conversational/short answers, consecutive questions, reopen/date change |
| A05 / A06 | Ranking criterion; metric replacement, filter retention/removal, ordering reversal, grouping change |
| A07 / A08 | Supported period comparison; unsupported percentage share |
| A09 / A10 | Revoked access and cross-tenant instruction override; quoted operation terminology |
| A11 / A12 | Conflicting aliases/correction; exact quoted free-form typed value |

Every turn checks cached replay, saved reports, source-file immutability and
payload isolation. A09 revokes scope before submission: denial is deterministic
and makes no model call. It tests access enforcement, not model refusal quality.
Catalog-change behavior is covered by existing Phase 07 tests; the new sample
adds no production metadata or synthetic host capability.

Independent truth reuses unchanged `phase05_reference.py` / `reference.py` over
synthetic Python/Decimal facts. V1 mistakenly composed an already implemented
comparison a second time. V2 corrects only A07's oracle composition; every question,
report goal and requested spec is retained. V1 freeze and first result remain.
The first Windows-only test decoding error was fixed by explicit UTF-8; no SDK
behavior or expected report was changed for a passing score.

## Contract check is not a live baseline

The one v2 offline contract check completed 8/14 trajectories and 8/16 required
reports; zero wrong accepted specs/unauthorized reads. A03/A04/A05/A06/A10/A11
remain incomplete. Several failures originate locally before any model stage;
the report separates these from scripted-transport limitations and cascading
failures. These supported report goals remain in the denominator. No SDK tuning,
scenario deletion or unsupported reclassification was used to improve results.
See `phase08/contract-check-first.v1.json`, `contract-check.v2.json` and the
[engineering report](../docs/PHASE08_ENGINEERING.md).

The wrapper delegates to the Phase 06 journal, budget, transport, scorer and
public SDK. Its existing post-turn hook checkpoints a safety violation before
stopping subsequent work: incorrect published report, wrong accepted spec,
unauthorized read or payload-isolation failure. Existing journal `runner_failure`
marks the stop; the scored turn retains the specific outcome. No alternate live
transport, retry mechanism, approval flag, accounting framework or model stage.

## Exact disabled approval packets

Provider: **AvalAI**, endpoint **https://api.avalai.ir/v1**, exact model identifier
**gpt-5-nano**, existing SDK Chat Completions adapter. Only those nonsecret config
fields were inspected; no key was read. The actual routed backend revision and
account-specific limits remain unverified.

| Limit | Pilot packet | Assessment packet |
| --- | ---: | ---: |
| Selected IDs | P01, P02 | A01–A12 |
| External requests | 12 | 120 |
| Input tokens | 250,000 | 2,000,000 |
| Output tokens | 49,152 | 491,520 |
| Total tokens | 299,152 | 2,491,520 |
| Per-call completion cap | 4,096 | 4,096 |
| Run elapsed seconds | 300 | 1,800 |
| Maximum estimated USD | $0.25 | $1.00 |
| Exact output directory | `D:\Coding\SageQL\dist\phase08\live-pilot-v1` | `D:\Coding\SageQL\dist\phase08\live-assessment-v1` |

Files: `phase08/approval-pilot.disabled.json` and
`phase08/approval-assessment.disabled.json`. Each binds ordered selected IDs,
merged answer-key selection hash, corpus/freeze/source/evaluator hashes, adapter,
endpoint/model and absolute directory. Both remain `authorized=false` with
pricing/accounting review disabled. No live output directory or live journal exists.
Both exact unauthorized preflight probes exit 2, with zero evaluation-key reads.

[AvalAI's model page](https://docs.avalai.org/fa/models/gpt-5-nano) lists standard
text rates of $0.05 input and $0.40 output per million tokens, and $0.005 cached
input. The packets carry those observed candidate rates, not a verified invoice
or account-specific worst-price guarantee. Worst-rate estimates do not discount
cache hits. Provider effective date remains REVIEW_REQUIRED. Published guidance
also warns that schema/framing and hidden reasoning affect token counts.
[Token-accounting guidance](https://docs.avalai.org/en/guides/token-counting).

Before approval, an operator must verify the model/route's full serialized-input
upper bound and framing allowance (4,096 overhead tokens is an **unverified
proposal**), reasoning-inclusive cap/usage accounting and absence of unpriced
fees. Public documents alone do not establish those guarantees. If they cannot
be established, live dispatch remains prohibited even if a user wants a trial.
Actual observed usage, conservative reserved estimates and provider billing are
different quantities. Cached/reasoning subsets must not be counted again.

## Execution procedure — not executed

First review the exact pilot questions, answers, hashes, synthetic permitted
catalog, output permissions, limits and pricing/accounting evidence. After explicit
human approval, retain a separate reviewed copy with its authorization reference
and verified pricing/accounting fields. Provision `SAGEQL_EVAL_API_KEY` through the
host secret mechanism; ordinary tests and draft generation never load `.env`.

```powershell
# Only after exact approval and accounting review:
.\.venv\Scripts\python.exe -m evaluations.phase08 --mode live --cohort pilot --endpoint https://api.avalai.ir/v1 --model gpt-5-nano --approval dist/phase08/pilot.reviewed.json --output D:/Coding/SageQL/dist/phase08/live-pilot-v1
```

Review every pilot first attempt before authorizing assessment. Advance only if
transport/schema, actual usage/reservations, scoring and journaling are technically
sound, there is no safety/bound violation, and the assessment packet has separate
exact approval. Missing usage must remain unavailable with conservative reserves;
unestablished accounting guarantees prevent further execution. A failed report
does not automatically invalidate an otherwise informative baseline. Do not switch
models, enlarge limits, retry to improve scores or silently substitute mocks.

Use the analogous `--cohort assessment` command with its separately reviewed packet
and directory. No across-run repetitions are included in these packets. Future
variability trials need distinct IDs/directories and explicit budgets. Existing
`--resume` rules retain all reservations/time, skip completed work and never replay
an uncertain turn. Changed source/corpus/configuration needs new reviewed packets.

## Offline verification commands

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_phase08_evaluations.py tests/test_phase06_evaluations.py -q
# Scripted contract exercise only, preserving a new first-attempt directory:
.\.venv\Scripts\python.exe -m evaluations.phase08 --output dist/phase08/contract-review-new
```

The current all-case contract command deliberately exits 1 for the retained
incomplete goals. The broader old regression commands still have their expected
exits. Completing preflight does not complete Phase 08's empirical objective.
