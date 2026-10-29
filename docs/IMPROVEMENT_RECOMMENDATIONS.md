# SageQL improvement recommendations

Prepared 2026-10-27 from a read-only review of the working tree (no code changed).
The goal is to make SageQL more reliably do its job: turn a manager's chat
message into the correct, authorized, deterministic report, quickly.

Sources reviewed: `agent-rules/Agent.md`, `README.md`, `docs/ROADMAP.md`,
`docs/SDK_AGENTS.md`, `docs/PHASE13_ENGINEERING.md`, `docs/PHASE14_ENGINEERING.md`,
`docs/RAHTAL_REAL_WORLD_EVALUATION.md`, `src/sageql/sdk/agents.py`,
`src/sageql/sdk/provider.py`, `src/sageql/sdk/engine.py`, and the outlines of
`evidence.py`, `phrases.py`, `grounding.py`, `business.py`, `intent.py`.

---

## 1. Where the project stands

**The deterministic half works.** No SQL-generation, policy or aggregation defect
was found in any completed live report. Authorization, parameterized compilation,
read-only execution, idempotent sessions and snapshot consistency are well built
and heavily tested (about 2,295 offline tests).

**The language-understanding half is the bottleneck.** In the evidence:

| Measurement | Result |
|---|---|
| Rahtal real-world, 10 manager questions (`gpt-5-nano`) | 2 PASS, 1 PARTIAL, 2 FAIL, 2 UNSUPPORTED-as-error, 2 BLOCKED (infra), 1 UNVERIFIED |
| Rahtal turn latency | median **71 s**, range 43–135 s, 42 model stage calls for 10 turns |
| Phase 13 live pilot | Reviewer approved **2 wrong** candidates; Planner invented grouping/ordering |
| Phase 14 live N01 | Reviewer approved **1 wrong** report (annual revenue instead of Sept units by department) |
| Phase 14 tokens | 8,256 of 8,702 completion tokens were **reasoning** tokens; 4 calls = 61 s |
| Cost | ~$0.004 for 4 calls, so cost is not the constraint |

Every observed failure was business interpretation: wrong period, lost context,
invented grouping/ordering, omitted output, or a long loop on an unsupported
request. Each phase then added a targeted local rule (regex evidence, a new
mismatch code, a new prompt sentence). That has made offline suites pass, but
live correctness on new wording has not been shown to improve. The project's own
reports say so: "Offline checks do not establish live-model generalization."

**Bottom line:** the next big gains come from changing the shape of the LLM
pipeline, the model choice and the evaluation loop, not from more safety layers.
The safety boundary is already strong. Keep it as it is.

---

## 2. Prioritized recommendations

Ordered by expected impact on correctness first, then latency. Each item keeps
the current product contract: models never write SQL, choose joins or see rows.

### P0-1. Put a stronger model on Intent, and set reasoning effort explicitly

*Evidence:* all live runs use `gpt-5-nano`, the smallest tier. Intent is the
single call that decides the report, and most failures start there (Phase 14
root cause: Intent call 1 returned an invalid partial period, and call 2 invented
annual revenue). No call sets `reasoning_effort` (`grep` finds none), so the
provider default is used. That is why reasoning tokens dominate output and calls
take 6–36 s each.

*What large agentic apps do:* **model routing**. A capable model handles the
hard, high-leverage decision, and cheap or fast models handle formatting,
classification and prose. Claude Code, Cursor and Perplexity all route by task
difficulty. OpenAI's agent guide says to "prototype with the most capable model
to establish a baseline, then swap in smaller models where they still pass the
evals."

*Recommendation:*
- Make model, and optionally reasoning effort, **configurable per stage**
  (`intent_model`, `planner_model`, `reviewer_model`). The `LLMConfig` and
  `OpenAIReportAgent` constructor already isolate transport, so this is a small
  API addition.
- Run the existing frozen Phase 08 v2 / Phase 14 N01–N06 corpora live with a
  stronger model (for example gpt-5-mini / gpt-5, or a Claude Sonnet-class model
  via an OpenAI-compatible endpoint) on Intent only. At ~$0.001 per call,
  even 10× the price is a few cents per report.
- Use explicit low reasoning effort for structurally simple stages. This could
  cut 50–80% of latency if accuracy holds; measure it rather than assume it.

### P0-2. Remove the Planner call by compiling Intent into a ReportSpec deterministically

*Evidence:* `ReportIntent` already contains nearly every `ReportSpec` field:
metrics, dimensions, period, comparison, filters, aggregate_filters, order_by,
descending, limit, chart, time_grain, comparison_calculation and
matching-day flag (`agents.py:653-672`). The Planner then asks the model to
**re-derive the same spec**, and a large local gate (`intent_feedback`,
`evidence_feedback`, `_OrderingSelectionError`, reconsideration) exists only to
catch the Planner **disagreeing with Intent**. Rahtal Test 08 failed after **four
`time_grain_mismatch` rejections**. That was the model arguing with itself, and
no report was produced.

*What large agentic apps do:* Anthropic's *Building Effective Agents* advice
is "find the simplest solution possible, and only increase complexity when
needed". Each LLM hop is a new chance to make an error. Text-to-SQL systems in
production (Snowflake Cortex Analyst, Databricks Genie, dbt Semantic Layer + LLM)
have the model fill a **semantic-layer query object** once. Deterministic code
then turns it into SQL. A second "planning" model is not used.

*Recommendation:*
- Add `spec_from_intent(intent, catalog, current_spec, today) -> ReportSpec | MissingDetail`,
  a pure function. It applies registered defaults (`default_metric_ids`, table,
  limit 100, null sort) and the existing canonicalizations: label/identity
  collapse, Jalali preservation and rolling windows.
- When it yields a valid spec, skip the Planner entirely. Only call a model to
  phrase a clarification or unsupported message, or generate those messages from
  templates. `measure_question`, `evidence_question` and `capability_reply`
  already do this locally.
- Expected effect: one fewer call (~18 s, ~4.5k input tokens in Phase 14). The
  `intent_mismatch` / `agent_exhausted` failure class largely disappears. Much of
  `intent.py:intent_feedback` and the reconsideration loop becomes unnecessary.

### P0-3. Replace the same-model Reviewer with a user-visible interpretation and parallel self-consistency

*Evidence:* across Phase 13 and 14 the Reviewer approved **3 of 3** observed
wrong candidates and was never seen catching a real semantic error live.
`SDK_AGENTS.md` itself notes the planner and reviewer "mistakes can be
correlated because they use the same model." It costs one serial call per
attempt, more with revisions.

*What large agentic apps do:*
- **Show the plan to the human.** Claude Code and Cursor have plan mode, ChatGPT
  data analysis shows its steps, and Cortex Analyst / Genie show "how I
  interpreted your question" with the generated query. The user is the cheapest
  and most accurate reviewer of *their own intent*.
- **Evaluator-optimizer only when the evaluator is stronger, or has different
  information.** A same-size model re-reading the same payload adds little.
- **Self-consistency / parallel sampling.** Sample the critical extraction
  N times in parallel and compare fields. Agreement gives confidence. A field
  where samples disagree is exactly the place to ask a clarification.

*Recommendation:*
1. Render every ready spec into a **deterministic natural-language
   interpretation line**, in Persian or English, using registered labels. For
   example: «مجموع واحدهای فروش به تفکیک دپارتمان، ۱ تا ۳۰ سپتامبر ۲۰۲۶، جدول».
   Return it in the reply JSON with the report, plus quick-edit chips (change
   period / measure / grouping). This also helps with wrong-period failures like
   Rahtal Test 02: the user would have seen "Azar/Aban" at once.
2. Replace the Reviewer call with **N=3 parallel Intent samples** (same latency
   as one call). Accept fields where all samples agree. Where they disagree on
   period, measure or grouping, ask a targeted clarification naming the
   alternatives.
3. If a model reviewer is kept, use a **different, stronger model** and a
   **field-by-field checklist schema**: `period_matches_user_words: bool` plus a
   quote, and so on. Do not use a free-form `approved` boolean.

### P0-4. Keep explicit dialogue state, not only a transcript

*Evidence:* Phase 14's main defect was context loss. The failed turn rolled back
the user message, so the year answer «Use 2026» arrived with no pending request,
and the model invented a report. Repairs added `pending_origin`, clarification
keys, `year_answer` heuristics and a "context-free year" guard in
`engine.submit`. Each turn re-derives meaning from raw text with ~1,800 lines of
en/fa regex (`evidence.py`, `phrases.py`, `grounding.py`).

*What large agentic apps do:* task-oriented dialogue systems (Rasa, Google
Dialogflow CX, Alexa skills) and modern agent frameworks (LangGraph state,
OpenAI Agents SDK context) keep a **typed state object**. A session holds a
*draft* of the task with each slot's **provenance**: user-stated,
inherited, defaulted or asked. Each turn is a *patch* to that draft.

*Recommendation:*
- Persist a `ReportDraft` in the session: every spec field plus provenance
  (`user_quote`, `turn_index`, `source = user|inherited|default|pending`) and the
  pending question slot.
- Intent then outputs a **patch against the draft**:
  `{set: {...}, remove: [...], answer_to_pending: ...}`. That is an easier task
  for a small model than restating the complete effective selection, which the
  current prompt demands in capitals.
- A failed turn keeps the draft and its pending slot even if the message log
  rolls back. This fixes the Phase 14 class of bug structurally rather than with
  a year-specific guard.
- Provenance also powers P0-3's interpretation line: "September (you said),
  2026 (you answered), grouped by Department (you said 'for each')".

### P1-5. Rewrite prompts: short, structured, example-led

*Evidence:* the Intent, Planner and Reviewer system prompts are each roughly
6–12k characters of concatenated rules (`agents.py:43-196`,
`provider.py:48-202`), mostly negations ("never", "do not") added after
individual failures. They overlap and partly conflict. For example, the
"COMPLETE effective selection" rule sits beside the refinement-preservation
rules. Small models follow examples much better than dense rule lists, and
negation-heavy text is known to be followed poorly.

*What large agentic apps do:* OpenAI and Anthropic prompting guides recommend
clear sections (XML or markdown tags), positive instructions, a short decision
procedure and **3–10 canonical worked examples** covering edge cases. Production
text-to-SQL systems get much of their accuracy from **retrieved few-shot
examples** (DAIL-SQL and similar research, Vanna's "training" Q→SQL pairs,
Genie example queries).

*Recommendation:*
- Structure each prompt as `<role>`, `<procedure>` (numbered steps),
  `<rules>` (≤15 positive rules), then `<examples>` (Persian and English).
  Include missing year, refinement, «برای هر», named month vs monthly grain,
  all data + latest N, unsupported share, and greeting.
- Delete rules that the deterministic code already enforces. The prompt should
  steer, and the validator keeps the safety boundary (`Agent.md` rule 4).
- Keep the static system prompt and catalog metadata **first** and the
  conversation **last** so providers' automatic prefix caching hits. Phase 14
  already shows 4,352 cached input tokens, so the order matters.
- Version prompts as files (`prompts/intent.v3.md`) with a hash recorded in
  evaluation evidence, so live results tie to an exact prompt.

### P1-6. Design the JSON schema for the model, not only for the validator

*Evidence:* the Intent schema has ~20 fields with nullable `anyOf` unions and
paired booleans (`comparison_specified`, `ordering_specified`, null vs empty
arrays meaning different things). Phase 14 call 1 returned a month with a null
year. The schema allowed a shape the validator then rejected.

*What large agentic apps do:* with structured outputs, **field order acts as
the model's scratchpad**. Put short evidence or reasoning fields *before* the
decision fields they justify. Use explicit enums instead of null-vs-empty
conventions.

*Recommendation:*
- Add `user_words_for_period` / `user_words_for_grouping` (short quotes) as the
  first properties. The decision fields follow. This is cheap reasoning that you
  can also check locally against the actual user text (the evidence layer
  already supports quote checks).
- Replace the null/empty/`*_specified` combinations with one tri-state enum per
  control: `"unspecified" | "set" | "remove"` plus a value.
- Make the period schema a discriminated union per kind, for example
  `{kind: "month", year: int, month: int}`, so a month without a year cannot be
  expressed. Add a separate `missing: ["year"]` path.

### P1-7. Add a verified-question library and semantic retrieval

*Evidence:* every Rahtal and synthetic host ships hand-registered vocabulary,
and the Phase 14 limits note says "Units" vs "Units sold" still depends on
interpretation. There is no store of known-good question → spec pairs, even
though the evaluation corpora and approved real sessions contain many.

*What large agentic apps do:* Snowflake Cortex Analyst's **Verified Query
Repository**, Databricks Genie's **trusted assets / example queries** and
Vanna's trained Q→SQL pairs all use the same pattern. Retrieve the most similar
verified examples and put them in the prompt. If a question closely matches a
verified one, reuse its spec directly. For large catalogs, retrieve only the
relevant concepts (**schema linking**) instead of sending the whole catalog.

*Recommendation:*
- Add a host-owned `VerifiedReport(question, spec, language)` registration,
  stored locally like vocabulary. It contains no rows and no physical names.
- Retrieve the top 3–5 by embedding or BM25 similarity (a local index is fine,
  and Persian needs a normalizing tokenizer; `phrases._NORMALIZE` already exists)
  and include them as few-shot examples in the Intent prompt.
- Add a "thumbs up/down + correct it" path in the frontend. Approved
  corrections become verified examples, so the system learns from each
  deployment without code changes.

### P1-8. Prefer one general report algebra over per-request extensions

*Evidence:* each new manager need became its own scoped extension with its own
doc, prompt text and code path: participant means, matching-day counts,
comparison changes, entity decreases, Jalali months, manager reports. Rahtal
gaps still include **percentage share, absence (no activity), per-group
top-N (partitioned ranking), series extrema**. These are standard analytics
primitives.

*What large agentic apps do:* semantic layers (dbt MetricFlow, Cube, LookML)
define a small, closed set of typed metric kinds: simple, ratio, derived,
cumulative, period-over-period and share-of-total. LLMs then compose those kinds
safely. No arbitrary formulas are needed.

*Recommendation:*
- Define one scoped design for a **closed typed operation set**:
  `share_of_total(metric, within=dimension?)`, `ratio(metric_a, metric_b)`
  between registered metrics only, `rank_within(group, metric, n)`,
  `anti_join_absence(entity_label, fact)`, and `extrema(series)`. Each is
  compiled deterministically with the same policy and group-before-limit rules.
- This would turn 3 of the 10 Rahtal questions (05, 07, 09) from unsupported or
  partial into supported. It also stops docs and `AGENTS.md` growing with every
  new question.

### P1-9. Fail fast and stay useful on unsupported requests

*Evidence:* the Rahtal absence request was the **longest** primary turn and ended
in `agent_exhausted` instead of a clear unsupported reply. Test 07 silently
omitted a requested percentage.

*Recommendation:*
- Run a **router** first: a cheap model call or the existing
  `operation_evidence` regex that classifies {greeting/capability, supported
  report, unsupported operation, refinement, answer}. Unsupported requests exit
  in one call with an explanation and the **nearest supported alternative**
  ("I can't compute share of total yet, but here are the totals by topic.
  Want that?").
- Never return a partial report without an explicit "not included: X" note in
  the reply JSON.

### P1-10. Make live evaluation a routine, statistical habit

*Evidence:* the offline evaluation infrastructure is excellent (frozen corpora,
independent Decimal references, scorers, replay, hashes). However, scripted
providers hide real failures: Phase 14 says "the scripted suite already supplied
a valid first Intent and therefore did not reveal the actual malformed-date /
context-loss path". Live runs have used 1–2 trajectories at a time, and each
needed a new approval packet.

*What large agentic apps do:* **eval-driven development**. A fixed live
regression set (50–200 cases) runs on every prompt or model change. Each case is
sampled several times to estimate pass rates (pass@1 and pass^k consistency),
with results tracked per stage over time. Paraphrase sets are generated by a
stronger model and reviewed by a human, to test generalization rather than
memorized wording.

*Recommendation:*
- One standing approval for a **synthetic-only** live budget, for example
  $5/month. At ~$0.004 per four-call turn that is over 1,000 turns. Run it
  nightly or per change with `python -m evaluations --live --samples 3`.
- Report per-stage accuracy (Intent field accuracy, clarification precision and
  recall, wrong-accept rate) with confidence intervals. Stop interpreting n=1.
- Keep a **blind holdout** written by someone other than the developer, never
  used for tuning, to measure real generalization.
- Track latency p50/p95 per stage next to accuracy, so P0-1/P0-2 changes are
  judged on both.

### P2-11. Latency engineering

- **Stream progress** to the frontend ("understanding… building query…
  running…"). Perceived latency matters for a 40–70 s turn.
- **Parallelize** independent work: Intent sampling (P0-3), label/lookup reads
  already batched by the engine, and catalog-metadata serialization cached per
  catalog digest.
- **Semantic cache**: key = (normalized message, draft-state digest, catalog
  digest). A repeated or near-identical question in the same scope returns the
  cached spec. Policies and execution are re-checked as usual.
- **Deterministic fast path**: when the local evidence layer fully determines the
  spec (simple "X by Y in month Z of year W"), compile directly and skip the
  model. The regex layers then become an accelerator instead of a second
  interpreter.
- Separate infra failures from model failures. Rahtal Tests 06 and 10 were
  blocked by SQL Server login and VPN. Add a cheap pre-flight connection check
  before spending a minute on model calls.

### P2-12. Simplify the code paths that grew by accretion

*Observations (no change made):*
- `AgentReportInterpreter.interpret` is about 270 lines with nested closures,
  lazy imports and several overlapping exit paths (`agents.py:357-627`).
  Turn it into an explicit **pipeline of stages over a state object**:
  `route → understand → compile → verify → present`. Each stage gets a typed
  result, which matches the observer events you already emit. LangGraph and the
  OpenAI Agents SDK model agents the same way.
- Evidence, grounding, phrases and business checks each parse the same user text
  independently. Parse it **once** into a `ScopedText` / evidence object per turn
  and pass that along.
- Lazy in-function imports (`from sageql.sdk.periods import ...` inside loops)
  hide dependencies and cycles. Resolve the cycles and move imports to module top.

### P2-13. Developer and agent ergonomics

- `AGENTS.md`, `agent-rules/Agent.md` and `ROADMAP.md` (108 KB) are long, dense
  and partly repetitive. AI coding agents load `AGENTS.md` every session, so
  every paragraph costs context and attention. Keep `AGENTS.md` to a short
  index of hard rules (≤100 lines). Move phase history to `CHANGELOG.md` and per-feature
  scope to the existing `docs/SDK_*.md`.
- The working tree has a very large uncommitted change set (25 modified, 200+
  untracked files, including phases 1–14). Commit in reviewable slices so each
  phase's evidence is tied to a commit hash instead of copied/hashed snapshots
  under `dist/`.

---

## 3. Suggested sequence

| Step | Change | Measure with |
|---|---|---|
| 1 | Per-stage model config + explicit reasoning effort (P0-1) | Live Phase 08 v2 + N01–N06, 3 samples, nano vs stronger Intent |
| 2 | Deterministic `spec_from_intent`, Planner optional (P0-2) | Same live set; expect fewer calls, fewer `intent_mismatch` |
| 3 | Interpretation line in reply + 3× parallel Intent sampling; Reviewer off by default (P0-3) | Wrong-accept rate, clarification precision, p50 latency |
| 4 | `ReportDraft` state with provenance and patch-style Intent (P0-4) | Multi-turn trajectories, Phase 14 N01 replay |
| 5 | Prompt rewrite with examples + schema reorder (P1-5, P1-6) | Same live set; prompt-version hash in evidence |
| 6 | Verified-report retrieval + feedback capture (P1-7) | Holdout set, Rahtal originals rerun on a stable snapshot |
| 7 | Typed operation set (P1-8), router/fast-fail (P1-9) | Rahtal 05/07/09 |

Steps 1–3 are small and reversible. Together they target most observed live
failures and roughly halve the number of serial model calls per turn.

## 4. What to keep exactly as it is

- Models never write SQL, choose joins or see rows or identities.
- Deterministic compilation, mandatory policies, explicit execution opt-in.
- Strict decoding of model output, fail-closed validation, no automatic DB retry.
- Idempotent request receipts, revision checks, snapshot read consistency.
- SQLite-first offline tests and independent reference calculations.

These are SageQL's real strengths. The recommendations above change *how the
request is understood*, never *what is allowed to execute*.

## 5. References (patterns, not code)

- Anthropic, *Building Effective Agents*: workflows vs agents, routing,
  parallelization, evaluator-optimizer, "start simple".
- OpenAI, *A Practical Guide to Building Agents* and structured-outputs /
  reasoning-effort documentation.
- Snowflake Cortex Analyst (semantic model + Verified Query Repository);
  Databricks AI/BI Genie (trusted assets, example queries, instructions).
- dbt MetricFlow / Cube / LookML: typed metric kinds in a semantic layer.
- Text-to-SQL research: schema linking, retrieved few-shot examples,
  self-consistency (DIN-SQL, DAIL-SQL, CHESS; BIRD and Spider 2.0 benchmarks).
- Task-oriented dialogue state tracking (slot filling with provenance), as in
  Rasa / Dialogflow CX and LangGraph state graphs.

Proposed commit message for this file:
`docs: add prioritized reliability and latency improvement recommendations`
