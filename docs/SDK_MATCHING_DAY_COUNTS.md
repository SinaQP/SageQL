# Matching daily group counts per registered entity

The tenth Rahtal request authorizes this fixed report operation. Set
`ReportSpec.include_matching_day_count=True` on a bounded, daily table report
with metrics and exactly one registered `EntityLabelDimension`. It adds the
integer `matching_day_count` field to every returned daily entity row.

The compiler first groups the policy-bound facts by date and registered entity
identity, then applies the selected aggregate filters, then counts those matching
daily groups per identity, before sorting/limiting. It uses one fixed SQL window
count in the same canonical SELECT. No model supplies SQL, formulas, partition
columns or join keys. Thresholds, selected metrics, dates and entity mappings
remain ordinary registered report concepts/typed conditions; no question text,
employee table, specific month or ten-hour threshold is hardcoded.

For ordinary two-period comparisons the partition includes the period label, so
each period has its own count. Fixed comparison changes/decreases, additional
dimensions, non-daily grains, charts, fieldless reports and unbounded periods are
unsupported with this operation. Filtering the computed day count itself is not
added: aggregate filters still reference selected registered metrics.

A null entity identity has an unknown day count, not one fabricated anonymous
employee spanning every anonymous day. Days with all-null measures remain unknown
under the existing SUM rules and do not pass a numeric greater-than condition.
Exactly-threshold totals do not pass a strict `gt` condition. Same display names
remain separate identity partitions; names are fetched only after output limits.
Mandatory fact/source policies, relationship cardinality guards, typed parameters,
timeouts, execution opt-in, metadata checks and cancellation remain unchanged.

The matching count covers every filtered day in the bounded period even when the
returned detail rows are truncated. Provenance explicitly records that scope;
the usual truncation flag still describes returned detail rows. Adapters must
return the additional typed field when selected. Invalid shapes fail closed.

The field is reserved and may be selected for ordering only while this operation
is enabled. False is the default, with no SQL or result changes to older report
shapes. Persisted legacy specifications lacking the additive flag remain readable;
new strict model schemas require it. The nullable intent flag permits older
provider-neutral backends. Local user evidence retains explicit matching-day
count requests and removal/refinement behavior; it does not parse a special
threshold or calendar conversion. Ordinary reports cannot acquire this column
merely because the capability exists. No report rows or identities enter model
context.

Non-goals: arbitrary windows, running totals, cross-grain joins, model-selected
partitions, historical identities/positions, computed-count filtering, new data
sources/objects, writes or a productivity judgment from long recorded days.

Verification commands:

```powershell
.venv/Scripts/python.exe -m pytest tests/test_sdk_matching_day_counts.py -q
.venv/Scripts/python.exe -m pytest -q
node tests/web_tabs.cjs
.venv/Scripts/python.exe -m build --no-isolation
```

Tests use synthetic sources and fake model transport, including a second business
catalog and variable thresholds/metrics. The configured Rahtal run and all five
earlier exact questions were independently checked against source rows; real
evidence remains ignored locally. A transient invalid planner response in the
decline regression failed closed; a subsequent run passed source verification.
