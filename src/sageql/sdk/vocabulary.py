"""Bounded local host vocabulary; no discovery, permissions or remote inventory."""
from datetime import date
from decimal import Decimal, InvalidOperation
import json
import re

from sageql.sdk.models import FilterValueDefinition, FullNameFilterDefinition, SDKError, json_value
from sageql.sdk.phrases import words


def same_value(left, right, family):
    if family == 'text':
        # JSON/storage converts accepted str subclasses (including string enums)
        # to plain str. Their scalar content still requires privacy projection.
        return isinstance(left, str) and isinstance(right, str) and left == right
    if family in {"integer", "decimal", "number"}:
        try:
            return Decimal(str(left)) == Decimal(str(right))
        except InvalidOperation:
            return False
    if family == "date":
        return (left.isoformat() if type(left) is date else left) == (right.isoformat() if type(right) is date else right)
    return type(left) is type(right) and left == right


def validate_values(definition, column):
    from sageql.sdk.semantics import _predicate, _text, _tuple, column_type
    code = "invalid_catalog"
    _tuple(definition.value_vocabulary, code, "Value vocabulary must be bounded.", maximum=64)
    if not definition.value_vocabulary:
        return
    if definition.value_vocabulary and (isinstance(definition, FullNameFilterDefinition) or "eq" not in definition.operators):
        raise SDKError(code, "Value vocabulary requires an ordinary equality filter.")
    family = column_type(column.data_type)
    seen = []
    for entry in definition.value_vocabulary:
        if not isinstance(entry, FilterValueDefinition) or entry.value is None:
            raise SDKError(code, "A typed value vocabulary entry is required.")
        _predicate(column, "eq", (entry.value,), code)
        if any(same_value(entry.value, value, family) for value in seen):
            raise SDKError(code, "Canonical vocabulary values must be distinct.")
        seen.append(entry.value)
        _tuple(entry.terms, code, "Vocabulary terms must be bounded.", maximum=8)
        if not entry.terms:
            raise SDKError(code, "Vocabulary terms must be nonempty.")
        terms = set()
        for term in entry.terms:
            _text(term, code, "Vocabulary terms must be bounded text.", maximum=120)
            normalized = words(term)
            if not normalized or normalized in terms:
                raise SDKError(code, "Vocabulary terms must be distinct after normalization.")
            terms.add(normalized)


def mapped_values(definition, literal):
    normalized = words(literal)
    return tuple(entry.value for entry in definition.value_vocabulary
                 if any(words(term) == normalized for term in entry.terms))


def _bindings(catalog):
    from sageql.sdk.semantics import column_type
    for di, dataset in enumerate(catalog.datasets):
        columns = {c.name: c for c in dataset.columns}
        for fi, definition in enumerate(dataset.filters):
            for vi, entry in enumerate(definition.value_vocabulary):
                yield (f"__sageql_value_{di}_{fi}_{vi}__", dataset.id, definition.id,
                       entry.value, column_type(columns[definition.column].data_type))


def _owner(value, inherited):
    if isinstance(value.get("dataset_id"), str):
        return value["dataset_id"]
    refs = [ref for key in ("metrics", "dimensions") for ref in value.get(key, []) or []
            if isinstance(ref, dict) and isinstance(ref.get("dataset_id"), str)]
    owners = {ref["dataset_id"] for ref in refs}
    return next(iter(owners)) if len(owners) == 1 else inherited


def project_payload(payload, catalog):
    """Replace canonical predicate slots, never the user's original conversation.

    References are meaningless outside this permitted catalog and structured
    input. No unselected aliases or canonical values are added to metadata.
    """
    bindings = tuple(_bindings(catalog))
    if not bindings:
        return payload
    if payload.get('conversation'):
        from sageql.conversation import Message
        from sageql.sdk.evidence import request_evidence
        from sageql.sdk.models import ReportSpec
        messages = tuple(Message(item['role'], item['text']) for item in payload['conversation'])
        current = ReportSpec.from_dict(payload['current_spec']) if payload.get('current_spec') else None
        evidence = request_evidence(messages, catalog, current)
        if evidence.filter_requirements:
            payload = {**payload, 'host_filter_requirements': [
                {'dataset_id': item.dataset_id, 'filter_id': item.condition.filter_id,
                 'operator': item.condition.operator, 'values': json_value(item.condition.values)}
                for item in evidence.filter_requirements]}
    def visit(value, owner=None):
        if isinstance(value, dict):
            owner = _owner(value, owner)
            result = {key: visit(item, owner) for key, item in value.items()}
            if isinstance(value.get("filter_id"), str) and isinstance(value.get("values"), list):
                replaced = []
                for scalar in value["values"]:
                    matches = [token for token, dataset, identifier, canonical, family in bindings
                               if dataset == owner and identifier == value["filter_id"] and same_value(scalar, canonical, family)]
                    replaced.append(matches[0] if matches else scalar)
                result["values"] = replaced
            return result
        if isinstance(value, list):
            return [visit(item, owner) for item in value]
        return value
    result = visit(payload)
    if result != payload:
        result = {**result, "host_value_reference_rule": VALUE_REFERENCE_INSTRUCTIONS}
    return result


def restore_response(payload, catalog, content):
    """Decode only references issued in actual structured input for that owner."""
    bindings = {token: (dataset, identifier, canonical) for token, dataset, identifier, canonical, _ in _bindings(catalog)}
    issued = set()
    def collect(value, owner=None):
        if isinstance(value, dict):
            owner = _owner(value, owner)
            if "filter_id" in value and isinstance(value.get("values"), list):
                issued.update((owner, value["filter_id"], item) for item in value["values"] if isinstance(item, str) and item in bindings)
            for item in value.values():
                collect(item, owner)
        elif isinstance(value, list):
            for item in value:
                collect(item, owner)
    collect(json.loads(content))
    def visit(value, owner=None):
        if isinstance(value, dict):
            owner = _owner(value, owner)
            if any(isinstance(value.get(key), str) and _REFERENCE_LIKE.search(value[key])
                   for key in ('question', 'message', 'unsupported_reason', 'feedback')):
                raise ValueError('Local value references are not display text')
            result = {key: visit(item, owner) for key, item in value.items()}
            if "filter_id" in value and isinstance(value.get("values"), list):
                restored = []
                for item in value["values"]:
                    if isinstance(item, str) and _REFERENCE_LIKE.search(item):
                        if item not in bindings:
                            raise ValueError("Invalid local value reference")
                        dataset, identifier, canonical = bindings[item]
                        if ((owner, value["filter_id"], item) not in issued
                                or dataset != owner or identifier != value["filter_id"]):
                            raise ValueError("Unissued local value reference")
                        item = json_value(canonical)
                    restored.append(item)
                result["values"] = restored
            return result
        if isinstance(value, list):
            return [visit(item, owner) for item in value]
        return value
    return visit(payload)


_REFERENCE_LIKE = re.compile(r'sageql[_\s-]*value', re.IGNORECASE)


VALUE_REFERENCE_INSTRUCTIONS = (
    " Predicate values such as __sageql_value_0_0_0__ are opaque host-bound scalar references. "
    "Copy a supplied reference unchanged for its supplied filter. Never infer its value, "
    "invent references or translate it. It is not a business label or SQL."
)
