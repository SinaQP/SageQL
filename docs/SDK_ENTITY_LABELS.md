# Registered entity labels

Outcome: grouped reports and top-N rankings can show names from an explicitly
registered profile source while preserving aggregation by identity. A name-to-ID
filter lookup is a different capability and does not enable this behavior.

The host registers an `EntityLabelDimension` on the report dataset. Its column
is the grouping identity, and its fixed source mapping declares a timeless
dataset, identity dimension, identity `in` filter and one to four text dimensions
in display order. The model sees only a text business dimension marked
`entity_label`; it cannot choose the mapping, SQL, expressions or joins.

The report SELECT groups, sorts and limits by the target identity and requested
metrics first. After that read, the engine fetches DISTINCT identity/name tuples
only for returned non-null identities, in batches of at most 100. Each source
read uses current source policies, metadata checks, parameter binding, execution
opt-in and the same request cancellation/deadline. At most one entity-label
dimension can be selected per report. The existing adapter row/query/work limits
also apply to each batch; source truncation fails closed.

Source and target dimension/filter permissions are mandatory. A denied mapping
is omitted from model metadata and rejected before execution if requested.
The engine checks the complete access fingerprint before and after every read.
Both sources remain separate single-source SELECTs; there is no cross-source
snapshot guarantee. No database object is created.

The engine replaces the selected label dimension's internal identity cells with
locally assembled text and declares the output field as text. Group membership,
metric values, ranking, row count and order stay intact. Identical names for
different identities remain separate rows. Identical duplicate profiles collapse;
conflicting nonempty names for one identity fail with `entity_label_conflict`
instead of selecting a candidate. Null identities, missing/blank/denied profiles
receive a generic unavailable-name label, never an unscoped retry or raw ID.
Sorting by a label dimension is unsupported: sorting before enrichment would
sort identities, and sorting after top-N would misrepresent the selection.

For explicit metric ranking, ties use the registered label's grouping identity
before remaining category dimensions, after period/time ties. Changing display
column order therefore preserves tied entity selection. Removing a registered
single-valued profile attribute also preserves that selection. Explicit primary
ordering remains authoritative; resolved labels never enter SQL ordering.

Refinements retain the selected dimension and frozen report dates and fetch
names again under current policies. Stored label cells contain displayed names,
and cached retries perform no reads. Database-returned names, resolved identities
and result rows never enter model context; persistent state still needs host retention/access
controls. Catalog changes invalidate earlier report compatibility fingerprints;
start a new chat after upgrading the Rahtal registration.

Non-goals: name-based grouping/merging, label-based filtering or alphabetical
top-N, fuzzy matching, arbitrary source relations, model-selected joins,
production identity/authorization, new tables/views or database writes.

Verification: offline synthetic SQLite results and deterministic SQL Server
compilation, policy/permission failures, duplicates/conflicts/missing labels,
bounded batches/truncation/cancellation, persistence/retries and provider payload
exclusion. Real model/SQL Server smoke checks are reported separately.
