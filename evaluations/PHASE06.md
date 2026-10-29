# Phase 06: live-agent evaluation readiness

**Phase 06 offline readiness complete; live-model reliability remains unverified.**
This assignment authorizes no external model requests. Keys/configuration and the
disabled example file do not authorize a trial. No production/Rahtal data is used.

## Offline commands

Run from the checkout with the existing virtualenv. Each run needs a new output
directory, preserving first outcomes and its durable journal:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_phase06_evaluations.py -q
.\.venv\Scripts\python.exe -m evaluations.phase06 --cohort all --output dist/phase06/all-first
.\.venv\Scripts\python.exe -m evaluations.phase06 --cohort assessment --output dist/phase06/assessment-first
.\.venv\Scripts\python.exe -m evaluations.phase06 --cohort development --output dist/phase06/development-first
.\.venv\Scripts\python.exe -m evaluations.phase06 --mode protocol --cohort protocol --output dist/phase06/protocol-first
.\.venv\Scripts\python.exe -m evaluations.phase06 --case L21 --output dist/phase06/retail-first
```

Exit 0 means every requested outcome was fulfilled, 1 means an incorrect or
unfinished trajectory/turn, 2 means configuration/preflight/runner failure. All
and assessment deliberately exit **1** for L26, whose second turn is still an
unfulfilled report. No waiver/xfail changes its goal or denominator. Development
and protocol pass. Ordinary tests explicitly assert that L26 remains a failing
evaluation outcome. Offline/protocol modes use mocks, never instantiate a remote
client, read an API key or load `.env`. A protocol pass is not model accuracy.

The new command extends the existing trajectory implementation, public SageQL,
real standard agent codecs, persistent SQLite sessions, policy-bound read-only
adapter, both offline SQL compilers and unchanged independent result scorer.
A Phase 06-only clarification check additionally requires a frozen alternative
term for the independently missing business detail. It is outside the wheel and
introduces no runtime dependency or reporting path.
Existing `python -m evaluations` commands and historical records remain intact.

## Corpus, independent truth and first outcomes

Fresh authored questions reuse workshop/retail/library host meanings and synthetic
facts. They do not copy the old question strings. The v4 corpus has **45
trajectories / 58 turns**: 26 assessment, five controlled development and 14
protocol trajectories. All 36 report goals have complete expected specs,
independent Python/Decimal source arithmetic, rows/types/order/bounds/presentation
and persistent/replay checks. Other goals separately declare ambiguity, missing
details, unsupported operations, denial, deliberate invalid output or failure.
No answer keys, expected rows or scorer results enter model requests.

All four input/freeze versions remain. V1 omitted `error_code` required by the
existing scorer for blocked outcomes; the first run stopped at that harness
error. V2 adds exact safe codes without changing questions, report answers or
outcome classifications. V3 additionally annotates each clarification with its
missing business detail and bounded keyword alternatives. The stricter wrapper
rejects a question about the wrong detail without changing report answers or
the historical scorer. These lexical checks do not prove arbitrary free-text
meaning; broader wording requires review. V4 retires L11 after independent contract
review: its explicit custom title is not a ReportSpec operation, so the old oracle
could not honestly credit complete fulfillment. Its entire case and prior outcomes
are preserved. Fresh assessment L27 uses a title example as quoted data without
requesting custom-title functionality. All other questions/goals/answers and cohort
counts remain unchanged. Before/after both use v4; no SDK title feature is added. The first mocks also incorrectly copied the request's
reference-instruction field into strict responses. The mock now returns only
response-schema fields. An initial unrelated-context probe accidentally used the
actually issued reference; its corrected fault uses the unissued source-owner
reference. Initial partial/full measurements are preserved as
`baselines/phase06_initial_v1.json` and `phase06_initial_v2.json`.

Inputs were frozen before execution of each revision. Every assessment has now
had offline exposure, but **none has live exposure**. Assessment L26 was not used
to implement a targeted semantic fix. Its `I mean Channel.` answer still safely
returns clarification_stalled, while its expected second-turn report remains.
Protocol/development probes supplied evidence for transport hardening. No new
live holdout is claimed to remain blind after a future model run; promote any
case used for targeted development and author/freeze a replacement before reuse.

Final all-corpus completion is 35/36 reports and 44/45 trajectories, with zero
incorrect accepted specifications. See the engineering report and separately
identified before/after/cohort records for exact counters and source hashes.
Original D03/D02 retain their historical report goals and incompletions.

## Protocol contract

References are issued only in currently permitted structured request predicates.
They are restored locally for their supplied dataset/filter, then undergo normal
intent/specification/evidence/access checks. The SDK rejects known-but-unissued,
wrong-owner, fabricated and altered reserved reference strings, including when
no vocabulary is visible. The reserved namespace `__sageql_value` (including case, leading-underscore
and separator alterations) cannot be used as an ordinary model-returned
filter literal. This narrowly changes invalid transport handling; ordinary
free-form values remain valid. Arbitrary text obfuscation is not a proven token
detector, and all ready specifications still need independent semantic checks.

References cannot appear in generated question/message/unsupported/reviewer
feedback text. A reference used as a metric ID fails ordinary concept validation.
Protocol probes distinguish issued reuse, omission, fabrication, alteration,
ownership, stale context, display text, malformed/duplicate-key JSON and extra SQL.
Canonical scalars remain accepted when they pass all ordinary semantic checks;
this protocol does not claim to force every correct scalar to arrive as a token.
Their observation is reported separately. Identical reference spelling reissued
in current context has current meaning; there is no claim to prove where copied
characters originated. Catalog/scope fingerprints still protect saved reports.

The model receives no new value/alias inventory, result rows, physical mappings,
policies, private lookup identities or credentials. User-entered terms remain
conversation text. Standard serializers are tested at intent/planning/review and
refinement. Custom providers remain trusted host code responsible for their own
external serialization. No trace export or raw-payload recording is introduced.

## Separate live preparation and approval

There has been no live authorization or trial. After a human chooses the exact
synthetic selection, reviewed endpoint/model and storage directory, generate a
**disabled** approval draft without constructing a client:

```powershell
.\.venv\Scripts\python.exe -m evaluations.phase06 --case L01 --endpoint https://reviewed-provider.example/v1 --model REVIEWED_MODEL --output D:/reviewed/sageql-trial-001 --prepare-approval dist/phase06/review-draft.json
```

Review the selected source/corpus/configuration hashes, questions, host metadata
and independent answers locally. The draft binds exact ordered IDs, source and
evaluator hashes, corpus/freeze, transport, endpoint/model and absolute output
directory. Set authorization only after separately explicit approval for that
exact evaluation. Supply a human authorization reference, all positive request,
input/output/total token, elapsed-time and USD ceilings, and per-call output cap.

Pricing needs reviewed HTTPS provenance without embedded credentials, effective
date, timezone-aware verification timestamp, USD/million-token units and worst
applicable input/output rates. Do not fetch or guess prices from this example.
Verify the provider's tokenizer/framing/schema overhead, output cap including
reasoning, usage accounting and absence of unpriced fees. The accounting
attestations are operator prerequisites, **not independent verification by the
runner**. If these cannot support conservative monetary accounting, do not
authorize the run. There is no certified invoice or universal hard billing cap.

Only after that approval, configure `SAGEQL_EVAL_API_KEY` through the host's secret
mechanism and use the separately explicit command (not executed in this phase):

```powershell
.\.venv\Scripts\python.exe -m evaluations.phase06 --mode live --case L01 --endpoint https://reviewed-provider.example/v1 --model REVIEWED_MODEL --approval dist/phase06/reviewed-approval.json --output D:/reviewed/sageql-trial-001
```

The placeholder endpoint/model are not approved. The CLI rejects absent/mismatched
approval, unreviewed pricing/accounting, unsafe endpoints, changed selections or
non-assessment fault scripts before accessing a key or constructing a client.
Only the existing SDK Chat Completions adapter is supported; compatible providers
use their reviewed endpoint. No vendor/model/format switching, retries, scripted
fallback or concurrency. SDK execution is synthetic SQLite only. No live readiness
test pings an endpoint. The existing older live procedure remains historical;
use this separately bound command for Phase 06 trials.

## Budgeting, interruption and resume

The journal durably reserves a request, full serialized UTF-8 request/schema plus
reviewed framing overhead, and maximum output tokens at worst reviewed prices
**before dispatch**. Observed complete valid usage adjusts reservations. Cached
and reasoning tokens are recorded as subsets, not charged twice; absent details
stay unavailable. Missing/inconsistent usage and failed/uncertain calls retain
reservations. Invalid usage or a provider bound violation stops further dispatch.
Budget tests use fictional prices, not evidence about real billing.

The remaining run time bounds transport, agent and SDK request deadlines. Wall
time includes pauses on restart. Native SDK/provider/driver cancellation remains
cooperative; the runner cannot forcibly terminate a provider ignoring its limits.
No failed database operation is retried. Unexecuted work is explicit; planned
completion denominators remain available alongside submitted-turn metrics.

An OS lock prevents simultaneous runs in one directory; atomic flushed checkpoints
preserve first results. After interruption, use identical configuration/approval:

```powershell
# Same reviewed mode, endpoint, model, selection, approval and directory as before:
.\.venv\Scripts\python.exe -m evaluations.phase06 --mode live --case L01 --endpoint https://reviewed-provider.example/v1 --model REVIEWED_MODEL --approval dist/phase06/reviewed-approval.json --output D:/reviewed/sageql-trial-001 --resume
```

Resume skips complete trajectories. A partially scored trajectory keeps prior
turns and is finalized interrupted; its uncertain call/turn is never repeated.
Only untouched trajectories continue, retaining all reservations and elapsed time.
If every turn was already durably scored, resume can finalize those existing
measurements without reexecution. An expired/exhausted budget is not reset.
Changed code, inputs, approval or selection requires a new reviewed experiment.
Keep output/journals under host-controlled permissions; local files are trusted
accounting state, not a tamper-resistant billing service.

## Measurement interpretation

All rates include exact numerators/denominators. Planned/attempted/unexecuted work,
first stages, raw/effective intent field checks, proposals, reviewer decisions,
deterministic rejection, bounded recovery, persistent state and cached receipts
remain distinct. Reviewer detection rates are unavailable if no wrong plan reached
review; local rejection before review is not reviewer success. Strict stage target
agreement can flag omitted optional/default fields; it is diagnostic, not an
independent live understanding score. Invalid protocol decoding cannot abort and
discard the SDK's already recorded safe failure.

Calls include failed dispatches; uncertain restart calls remain in durable budget
counts even when per-turn diagnostics could not be saved. Coverage is explicit.
Record local adapter and stage/recovery timing separately. Adapter time includes
local compilation checks and SQLite execution; recovery time sums flagged model
calls and excludes local validation/setup; scripted milliseconds
are not remote latency or production SQL Server measurements. Token/cost values
are unavailable for ordinary scripts; fictional unit-test usage is not a live
measurement. Local cost estimates/reservations remain distinct from provider
invoices, which are unavailable. Clarification turnaround is unmeasured.
