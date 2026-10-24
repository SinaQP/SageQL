# Bounded entity decline rankings

The explicit third Rahtal question authorizes a fixed identity-aligned decline
ranking beyond ungrouped changes: `comparison_calculation="decrease"`, one
registered `EntityLabelDimension`, one numeric sum/count aggregate, two bounded
periods, a table, no time grain/aggregate filters. `order_by="absolute_decrease"`
and `descending=True` mean largest absolute loss first, not percentage ranking.
Without a requested count, the local intent guard uses the ordinary 100-row
output default; the two comparison periods are not a two-entity result limit.
Unchanged refinements preserve the current output limit.

The existing compiler groups each period by registered identity under the same
mandatory policies/user filters. The candidate limit is the host's
`ExecutionLimits.max_rows`, independently of the output limit. Read the complete
union of period groups within this finite cap; truncation fails closed and cannot
produce a purported top-N. No model formula, join, SQL expression, database
object or unbounded read is introduced.

Align groups locally by identity, never name. A missing group in a complete period
means no qualifying rows, so additive sum/count is zero. An existing null SUM
remains unknown. Only non-null identities with positive reference and known
strictly lower current value qualify. Exclude null identities, unknown values,
nonpositive references and non-decreases with category counts in provenance.
Empty output is valid. Duplicate identity/period rows or malformed values fail.

Positive absolute loss is reference minus current; percent loss is
loss/reference*100 before rounding in the comparison-change Decimal context.
Sort precise loss descending, breaking ties by registered integer/text identity,
then apply the output limit. Mark output truncation when more eligible groups
exist; source truncation is an error. Resolve names only for selected identities
via existing bounded policy-bound label reads. Equal names remain separate;
conflicting profiles fail. No result/identity enters model context or provenance.

Output columns: entity label, reference/current values, absolute/percentage
decrease. Preserve metric units/types and period captions. Provenance records the
fixed ranking/denominator, candidate/eligible counts and excluded category counts.
Access checks, execution opt-in, deadline, receipts, refinements and stored reports
retain SDK rules. Existing separate source reads have no cross-source snapshot.

Non-goals: arbitrary dimensions/relations, multiple metrics, average/min/max zero
filling, time alignment, percentage ranking, arbitrary formulas, profile-universe
zero rows, fuzzy names and production employee authorization.

Verify offline SQLite execution/T-SQL compilation, absolute versus percentage
order, ties/equal names, missing-month versus null, policies, caps/truncation,
invalid adapter rows, labels, persistence/retries and model payload exclusion.
Keep real runs and independent source checks ignored locally.
