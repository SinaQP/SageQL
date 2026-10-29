# Optional host-owned filter value vocabulary

Phase 06 tightens invalid transport handling: fabricated or altered strings in
the reserved `__sageql_value` namespace (including case/hyphen variants tested)
are rejected rather than treated as free-form values. References are also forbidden
in reviewer feedback. Ordinary free-form business literals remain supported;
canonical scalar responses still require all existing semantic checks.

Designed 2026-10-25; this document defines the scoped contract.

## Decision and alternatives

Extend the existing `FilterDefinition` with keyword-only optional
`value_vocabulary: tuple[FilterValueDefinition, ...] = ()`. A value entry contains
one typed canonical `value` and explicitly accepted `terms`. Registration stays
with the filter that owns its meaning. Existing positional constructors, including
`FullNameFilterDefinition.name_columns`, keep their positional meaning.

A catalog-wide registry would duplicate owner/filter references and add another
projection path. A callback resolver adds authorization, timeout, failure and data
read contracts without evidence it is needed. Neither is selected. No resolver,
database discovery, runtime dependency or second catalog is introduced.

## Host contract

Example (existing physical columns and access rules still belong to the host):

```python
from sageql.sdk import FilterDefinition, FilterValueDefinition

channel = FilterDefinition("channel_filter", "Channel", "channel",
    value_vocabulary=(FilterValueDefinition("Web", ("Web", "Online", "آنلاین")),))
shelf = FilterDefinition("shelf_filter", "Shelf", "shelf_name",
    value_vocabulary=(FilterValueDefinition("Science", ("Science", "Scientific", "علمی")),))
```

Only ordinary registered scalar filters accepting equality may carry vocabulary.
Canonical values use existing scalar/predicate validation (text, integer, boolean,
decimal/number, date); null/timestamp and name-lookup definitions are excluded.
The canonical value is never case-folded, whitespace-normalized or converted from
an alias. Normalization applies only to matching terms. Exact word boundaries,
existing quote roles, clause polarity and explicit predicate roles still apply.

Bounds: 64 entries/filter, eight nonempty terms/entry, 120 characters/term;
catalog maximum 1,024 entries/4,096 terms. Reject malformed tuples, invalid scalar
types, duplicate canonical values and redundant normalized terms within one entry.
Shared aliases across distinct values/filters are valid ambiguity, not priority.
There is no mandatory static enum: unknown free-form values remain valid when the
user supplies a registered owner and compatible typed literal.

An explicit owner constrains alias selection to that filter. Otherwise uniquely
eligible host vocabulary can establish the owner only in a bounded row-selection
role (`for`, `only`, `exclude` and supported Persian equivalents). Mere mentions,
metric/dimension names, titles/examples do not create predicates. Ambiguous values
clarify. A user owner answer binds the original literal, preserving earlier report
requirements. Conflicting predicates clarify; replacements/removals/refinements
use the existing typed control contract, never provider guesses.

Registered dimension-filter imports inherit the source vocabulary through their
existing directed relationship. Both target and source permissions must remain
available. Register on the physical source before registering relationships.

## Authorization, privacy and model boundary

Permission projection removes unavailable filter definitions and their vocabulary
before local matching. The registry grants no capability, dataset or row access.
No global caches mix actors/catalogs. Every ready provider result remains checked
against the original request before lookup/report reads. Omitted/wrong predicates
are rejected or repaired within existing bounds; custom-provider omissions block.

All new vocabulary is **local-only**. There is no opt-in sharing flag in this
slice and no inventory of values/aliases is sent through `_metadata`. User-entered
terms continue to be user text; unrelated host terms and private canonical values
must not be introduced into model context via intent, planning, review or current
specification on a subsequent turn.

For the standard model transport, predicate slots containing registered canonical
values use opaque local value references on the wire. They reveal no canonical
value or alias inventory. Only references actually issued in structured request
context can be decoded for their own permitted filter. Restore canonical typed
values locally before validation/execution; never send a restored value back in
a later stage. These references are transport-internal, not new ReportSpec fields,
business values, SQL parameters or stored session state. Canonical values persist
locally in normal typed specs and are bound as existing SQL parameters.

Locally grounded predicates are supplied as protected references from the first
standard call, including the older single-interpreter path. They are runtime host
evidence, not evaluation answer keys. Unissued/wrong-owner references and references
in generated display text fail safely. Matching string-enum content is protected
after JSON persistence as well.

Custom providers/backends are trusted host code, as before: Python catalog/spec
objects contain host semantics. They must curate any external serialization.
The standard remote serializer enforces local-only vocabulary and value references.
Safe errors/observer/evaluation output exclude rejected/canonical values and aliases.

## Revisions and compatibility

The complete catalog fingerprint includes vocabulary. Changing it invalidates
stale saved-report/cache scope compatibility; no receipt or stored report is
silently re-executed. A host should version material registration changes and use
a new session when appropriate. No session schema change is planned. Current access
is rechecked before cached/saved access and execution.

Original D03 keeps the original catalog and its unfulfilled one-turn report goal:
safe clarification, zero reads. A separate versioned workshop host with a declared
Web-to-Channel entry should complete the same request with 580, independently
verified from synthetic source records. It is a different metadata condition.

## Acceptance and non-goals

Freeze separate development/assessment inputs before execution. Verify three
independent domains, typed values, aliases/collisions, free-form values, policy/
relationship projection, every provider gate, bounded repair, persistent multi-turn
contexts, replay/revocation and canonical parameter spelling. Preserve all previous
corpus/freeze/baseline bytes. Measure resolution overhead without a production SLA.
No live calls, production data/objects, new analytics, arbitrary resolver, public
result format, permission changes or Phase 06 work.
