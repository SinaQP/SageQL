"""Explicitly versioned synthetic vocabulary hosts; never alter older fixtures."""
from dataclasses import dataclass, field, replace
from datetime import date
from decimal import Decimal
import json
from pathlib import Path

from sageql.sdk import FilterDefinition, register_relationships
from evaluations.phase03_hosts import host as original_host

try:
    from sageql.sdk import FilterValueDefinition
except ImportError:
    # Before-measurement compatibility only: starting SDK accepts FilterDefinition
    # subclasses but does not consume these passive host declarations.
    @dataclass(frozen=True)
    class FilterValueDefinition:
        value: object = field(repr=False)
        terms: tuple = field(repr=False)

    @dataclass(frozen=True)
    class UnconsumedValueFilter(FilterDefinition):
        value_vocabulary: tuple = field(default=(), kw_only=True, repr=False)


ROOT = Path(__file__).with_name("phase05")


def host(domain, version):
    catalog, policy, create_data = original_host(domain)
    if version == "original":
        return catalog, policy, create_data
    profiles = json.loads((ROOT / "hosts.v1.json").read_text(encoding="utf-8"))["profiles"]
    profile = profiles[version]
    if profile["domain"] != domain:
        raise ValueError("Vocabulary host/domain mismatch")
    relationships = catalog.relationships
    datasets = []
    for dataset in catalog.datasets:
        # Register on existing physical source concepts before public expansion.
        physical = tuple(f for f in dataset.filters if f.column not in dataset.related_columns)
        if domain == "workshop":
            physical += tuple(FilterDefinition(*values) for values in profile.get("extra_filters", []))
        definitions = []
        for definition in physical:
            entries = []
            for owner, identifier, kind, value, terms in profile["values"]:
                if owner != dataset.id or identifier != definition.id:
                    continue
                value = Decimal(value) if kind == "decimal" else date.fromisoformat(value) if kind == "date" else value
                entries.append(FilterValueDefinition(value, tuple(terms)))
            if entries:
                definition = (replace(definition, value_vocabulary=tuple(entries)) if hasattr(definition, "value_vocabulary") else
                              UnconsumedValueFilter(definition.id, definition.label, definition.column, definition.operators,
                                                    value_vocabulary=tuple(entries)))
            definitions.append(definition)
        datasets.append(replace(dataset, filters=tuple(definitions),
            columns=tuple(c for c in dataset.columns if c.name not in dataset.related_columns),
            dimensions=tuple(d for d in dataset.dimensions if d.column not in dataset.related_columns), related_columns=()))
    catalog = replace(catalog, datasets=tuple(datasets), relationships=(), version=catalog.version + ":" + version)
    return register_relationships(catalog, relationships) if relationships else catalog, policy, create_data
