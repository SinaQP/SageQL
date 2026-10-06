# Registered employee-name resolution

User outcome: an activity request naming an employee resolves that person from
the approved profile source, without asking the user for an internal ID.

This scoped extension permits one host-registered entity lookup per report:
an equality match on a registered full-name filter, optionally narrowed by
registered qualifiers such as job position, followed by a single-source report
filtered by the unique returned identity. It introduces no joins, database
objects, arbitrary expressions, fuzzy matching or model-written SQL.

The host declares the source dataset, identity dimension, full-name filter,
optional qualifier filters and the target equality filter. Source/target scalar
types must agree. A full-name filter combines two to four registered text
columns in declared order and uses fixed whitespace/ZWNJ and Persian/Arabic
letter normalization. Its entire normalized name is compared for equality;
no substring or approximate match selects a person.

The model receives permitted business labels and virtual name/qualifier filter
IDs. It returns literal user names in ordinary UserFilters. It never receives
lookup result rows or the resolved identity. Original name filters remain in
conversation specifications and report display metadata; the concrete identity
filter stays in the internal execution/saved validation specification.

A named activity request with a period defaults to the registered daily measures
and a table when the user has not selected a particular measure. The request
already permits the registered name lookup; prior assistant questions do not
create a requirement for an internal ID or permission to search. The configured
interpreter recognizes ID/search-confirmation questions in Persian and English
and makes at most one corrective interpretation with the same permitted payload
and the remaining original provider deadline. Both responses undergo the normal
strict decoding, and the engine validates the resulting specification before any
read. Malformed output or transport failures are not retried. A second such
question returns a safe, retryable `clarification_stalled` error instead of
repeating the question. This targeted UX check is not a general natural-language
correctness guarantee or an authorization boundary. Genuine missing business
details remain questions; host-generated missing/ambiguous-match clarification
does not go through this correction.

Lookup reads use the existing deterministic compiler and adapters, current
source policies, metadata checks, explicit execution opt-in, parameter binding,
row/time/work/concurrency/cancellation limits and disposable connections.
Each query is a separate bounded SELECT on one registered source. Access is
checked before and after each read and again around final execution. Identity
is a report filter, never authentication or an expansion of target access.
This is not a cross-source snapshot transaction; names can change between reads.

The lookup selects DISTINCT identity values with a two-candidate limit.
Duplicate profiles for one identity cannot multiply activity aggregates. Zero
matches ask the user to correct the name. Multiple identities, truncation or
invalid lookup results never select the first candidate. Ambiguous matches ask
for a registered qualifier, without forwarding stored names/roles to the model.
Names and result values stay out of logs and diagnostic scalar parameters remain
redacted. Lookup SQL must also redact its name bind; no extra unfiltered probe.

Persistent refinements keep names/qualifiers and frozen periods, re-resolve the
name under current access, and reapply target policies. Completed retries reuse
their existing receipt without repeating either read. Saved reports still require
the current catalog and complete access-scope fingerprint to match.

Acceptance: unique and duplicate names, Persian letter/spacing variants, missing
names, qualifier refinement, denied source/target access, malformed model output,
execution disabled, truncation, policy change between reads, retries and session
reload are covered offline. Rahtal registers only its existing profile/activity
columns. A request for all daily activity information selects its registered
daily measures; unregistered descriptions or raw activity detail are not invented.

Verification on 2026-10-06: the full offline suite passed (514 tests, one optional
synthetic SQL Server check skipped). Isolated package builds and fresh-wheel
imports passed. A configured-model interpretation of the user's Persian name
request succeeded after one separate invalid-output attempt; executing its
validated specification on the existing SQL Server returned 27 daily report rows
through the two policy-bound reads. These results establish that one real
request's lookup/metadata/execution path works; they do not guarantee every
natural-language interpretation or activity total.

Clarification regression command (offline):

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_sdk_provider.py tests/test_sdk_lookups.py -q
```
