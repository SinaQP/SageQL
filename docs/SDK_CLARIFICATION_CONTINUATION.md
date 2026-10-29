# Scoped clarification continuation

Designed 2026-10-26 and updated with verified reset/unsupported-operation rules.

## Outcome and scope

A confirmed answer resolves only its pending business slot. Original metrics,
grouping, predicates, literal/canonical values, periods/comparisons, exclusions,
sort and limit remain applicable until the user explicitly changes them or starts
a new report. Models and assistant suggestions cannot establish missing meaning.
Only currently permitted registered concepts are eligible.

L26 first loses its original evidence: an ownerless fallback begins at `For July`
and masks date/measure/grouping while replacing the already recognized ambiguous
Portal operand. Its answer then fails an exact-label/use-label check. Fix both
responsibilities; broadening the answer alone would bind a corrupted literal.

## Selected design and alternatives

Keep existing messages, pending origin/question/key and typed current report.
The stores correctly preserve those values and roll back failed turns; a new
persistent schema, versioned state migration or orchestration framework is not
justified. Reconstruct only known local pending targets from user evidence under
current access, using a shared bounded answer-role recognizer.

The recognizer matches registered labels/existing metric selection terms in
short affirmative choice clauses, including tested English/Persian conversational
wrappers. Negative choices do not select a complement. Multiple positive choices,
unknown owners, questions and unconfirmed quotations remain unresolved. Explicitly
confirmed quoted labels may select a concept; a quoted missing text-filter value
remains exact data. No new owner-alias registry or inferred translation is added.

Consumed owner-choice clauses are not output grouping/metric instructions.
In particular rejecting Service as an owner cannot remove Service grouping.
Mask consumed source spans without changing other literals' case, Unicode or
whitespace; process remaining explicit instructions with existing semantics.

Reuse the same contextual choice recognition for demonstrated registered metric,
dimension and sort-target answers. Existing date/grain grammars remain responsible
for periods, rather than introducing a general language parser. Missing-value
answers bind only the known filter and preserve exact quoted data. Canonical
vocabulary resolution remains local and uses existing typed validation.

## Preservation and safety

Phase 09 retains bounded unresolved slot/reason pairs internally. Resolving an
owner does not supply a year, and resolving a metric does not choose a grain.
Independent affirmative clauses can explicitly supply more than one detail.
Question clauses remain unconfirmed without suppressing a separate affirmative
answer. Date clarification retains the existing provider flow; it no longer
inherits a filter or grouping reason by accident. No session JSON changes.

Imported/source dimensions with the same registered business origin retain
alternative permitted grouping requirements until intent selects the fact. The
final gate requires its matching grouping, including for custom providers. It
does not invent a dataset, measure or relationship.

Explicit sort directions govern a top/bottom row count. A sort-target answer keeps
the prior limit unless its own clause supplies a new limit. Scoped replacements
exclude the old concept and require the new one. Metric choices preserve other
independent measures and reject unrequested extras. Explicit plural filter
retention preserves the exact typed filter set, and date-free refinements retain
their frozen current period. New date/comparison instructions still apply.

Plural quote/example wording follows the existing literal-role rules. An
affirmative named-filter assignment can use terminal `instead` as a correction
modifier; quoted values keep that word and their exact Unicode/spacing as data.
Unissued opaque references remain invalid.

Known vocabulary operands take precedence over fallback unknown-value scans.
Fallback operands cannot span registered requirements or mask date/group prose.
Unresolved answers preserve the pending request; existing stalled-clarification
limits still bound repeated non-progress. Valid answers must not hit that guard.
Unsupported operations in another clause remain unsupported. Explicit new-report
instructions form a context boundary and do not inherit pending controls.
The reset marker follows only the outstanding clarification chain; later normal
refinements use the current report. For that new report, the final gate rejects
unrequested predicates, ordering/direction and non-default limits. A question
about starting over is not a reset instruction. Known-filter value resolution
does not erase an unsupported operation in a separate clause.

Deterministic evidence constrains effective intent, planning and every final
provider result before reads. Incorrect proposals may recover within existing
limits or block; reviewer approval grants no authority. Current catalog/scope
checks, execution opt-in, parameterized SQL, atomic publication and request replay
remain. No automatic failed/uncertain database retry, extra model stage, new
analytics, permissions, production database work or external model call.

## Evidence and evaluation

Preserve original Phase 06 v4 and measurements. Exact L26 is promoted unchanged
to development; an independently authored library replacement and cross-domain
cases are frozen before repair. Compare original and new populations separately,
score every turn and complete data/state, and retain all unexpected failures.
No real-model generalization claim follows from scripted transport tests.
