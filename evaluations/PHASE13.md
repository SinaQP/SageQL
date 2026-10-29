# Phase 13 live evaluation

Ordinary evaluations and pytest remain offline, use synthetic SQLite and never
load model credentials. Native SQL Server tests remain separately disabled.
The current results and scope are in [the engineering report](../docs/PHASE13_ENGINEERING.md).
Earlier disabled packets and the accounting-blocked `phase13/verification.v1.json`
are historical evidence; they are not enabled by this option.

## Accounting modes in the existing runner

`--accounting-mode strict` is the default. Its exact approval schema, reviewed
input bound, reasoning-inclusive accounting and no-unpriced-fees attestations
remain required. An exploratory packet cannot pass the strict validator.

`--accounting-mode exploratory` is an explicitly authorized alternative. Both the
command and exact source/corpus/endpoint/model/output-bound packet must select it.
It requires `accepts_billing_uncertainty=true`. This is not permission inferred
from an API key. Drafts always remain disabled and decline uncertainty acceptance.

The exploratory packet uses the same request/token/elapsed/estimated-cost limits,
durable pre-dispatch reservations and no-retry transport. It records published
prices with `observed_date`, without claiming a provider effective date. Its
accounting fields are:

```json
{
  "input_estimate": "serialized_utf8_bytes_plus_overhead",
  "overhead_tokens": 4096,
  "guaranteed_bound": false,
  "provider_billing_verified": false
}
```

Input reservation is a local estimate, including serialized messages/schema and
an estimated framing allowance. Observed usage replaces reservations; an input
estimate overrun remains visible as variance. Invalid/missing usage, transport
failure, output-cap violation or exhausted limits stop subsequent dispatch.
Unknown usage retains its reservation. Cached/reasoning tokens are subsets;
they are not added again. Prices use the full input rate, with no cache discount.
The estimated USD stop cannot guarantee account charges or terminate work already
being processed remotely. No invoice or reasoning-inclusive billing guarantee is
fabricated. HTTP/agent/SDK deadlines are finite, with no automatic failed DB or
model transport retry.

## Commands

Create a disabled source-bound draft in a fresh path:

```powershell
.venv/Scripts/python.exe -m evaluations.phase08 --cohort pilot --endpoint https://api.avalai.ir/v1 --model gpt-5-nano --accounting-mode exploratory --prepare-approval dist/review/pilot.json --output C:/approved-local-output/pilot
```

Review the exact selection, source hashes, synthetic scope, public price evidence,
finite limits, output directory and explicit human authorization before enabling
the packet. Provision only `SAGEQL_EVAL_API_KEY` to the live process. The runner
does not load `.env`; do not provision production database configuration.

```powershell
python -m evaluations.phase08 --mode live --cohort pilot --accounting-mode exploratory --endpoint https://api.avalai.ir/v1 --model gpt-5-nano --approval dist/review/pilot.json --output C:/approved-local-output/pilot
```

The absolute output directory must exactly match the packet. A changed source or
experiment requires a new packet and directory. Never resume a failed baseline
to erase its first attempt. The Phase 08 safety hook checkpoints a wrong accepted
report before stopping later work. Preserve and investigate it; separately label
any engineering comparison authorized by the user.

`capture_responses=true` explicitly enables bounded local visible assistant-output
recording under `responses/call-NNNN.json` for synthetic evaluation only. It is
off in drafts and absent from strict mode. Recording excludes HTTP headers,
credentials, request payloads and exception bodies; raw visible output is not
copied into public summaries. Use ignored local outputs with appropriate access.
Do not share private model reasoning. A recording failure stops further calls.

## Offline verification

```powershell
python -m pytest tests/test_phase13_exploratory.py tests/test_sdk_tabular_periods.py -q
python tools/release_check.py offline --source . --output dist/new-offline/results.json
```

The shared retail/library/workshop builders, frozen questions/answers and
independent references are reused. Live P01/P02 is a small exploratory population;
it cannot establish clarification quality, opaque-reference reliability or broad
generalization. SQLite cannot verify native SQL Server/ODBC/isolation guarantees.
