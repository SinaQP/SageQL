"""Independent Python oracle: no SageQL imports, SQL or generated results.

The workshop reference consumes authored source records. Retail/library records
below independently restate their authorized September source facts and host
relationship meanings. They are not imported example.expected answers.
"""
from collections import defaultdict
from decimal import Decimal
import json
from pathlib import Path


def facts(domain):
    if domain == "workshop":
        data = json.loads((Path(__file__).with_name("phase03") / "records.json").read_text(encoding="utf-8"))
        return [dict(zip(data["columns"], row)) for row in data["rows"]
                if row[0] == "blue" and row[1] == 0]
    if domain == "retail":
        return [dict(completed=d, department=g, revenue=n, units=u) for d, g, n, u in (
            ("2026-09-01", "Books", 30, 2), ("2026-09-02", "Books", 40, 3),
            ("2026-09-02", "Garden", 45, 9), ("2026-10-01", "Books", 700, 70))]
    if domain == "library":
        return [dict(completed=d, shelf=g, loan_days=n) for d, g, n in (
            ("2026-09-01", "History", 14), ("2026-09-01", "Science", 2),
            ("2026-09-02", "Science", 6), ("2026-09-03", "Science", 10),
            ("2026-10-01", "History", 700),
            # A source policy hides the dimension, not this visible fact.
            ("2026-09-01", None, 600))]
    raise ValueError("Unknown reference domain")


def expected_report(domain, spec, bounds):
    """Only independently scoped operations used by this corpus, fail on others."""
    if spec.get("comparison"):
        selection = spec["comparison"]
        year, month = selection["year"], selection["month"]
        start = f"{year:04}-{month:02}-01"
        end = f"{year + (month == 12):04}-{month % 12 + 1:02}-01"
        plain = {**spec, "comparison": None, "order_by": None}
        base = expected_report(domain, plain, bounds)
        other = expected_report(domain, plain, [start, end])
        return {**base, "fields": ["period_label", *base["fields"]],
                "types": ["text", *base["types"]],
                "rows": [["base", *base["rows"][0]], ["comparison", *other["rows"][0]]]}
    metrics = {"billed": ("sum", "fee"), "jobs_count": ("count", None),
               "minutes_total": ("sum", "minutes"), "minutes_mean": ("average", "minutes"),
               "revenue": ("sum", "revenue"), "units": ("sum", "units"),
               "borrowings": ("count", None), "mean_duration": ("average", "loan_days")}
    rows = [row for row in facts(domain) if bounds[0] <= row["completed"] < bounds[1]]
    for predicate in spec.get("filters", []):
        field = predicate["filter_id"].removesuffix("_filter")
        operator, values = predicate["operator"], predicate["values"]
        if operator not in {"eq", "in"}:
            raise ValueError("Reference operator is outside this corpus")
        rows = [row for row in rows if row[field] in values]
    dimensions, metric_ids = spec.get("dimension_ids", []), spec["metric_ids"]
    grain = spec.get("time_grain", "none")
    if grain not in {"none", "day", "month"}:
        raise ValueError("Reference grain is outside this corpus")
    fields = (["time_bucket"] if grain != "none" else []) + dimensions + metric_ids
    groups = defaultdict(list)
    for row in rows:
        key = tuple(row[key] for key in dimensions)
        if grain != "none":
            key = ((row["completed"] if grain == "day" else row["completed"][:7] + "-01"), *key)
        groups[key].append(row)
    if not dimensions and grain == "none":
        groups[()] = rows
    result = []
    for key, members in groups.items():
        aggregates = []
        for metric in metric_ids:
            operation, column = metrics[metric]
            values = [Decimal(str(row[column])) for row in members] if column else []
            value = len(members) if operation == "count" else sum(values) if values else None
            if operation == "average" and values:
                value /= len(values)
            aggregates.append(value)
        result.append([*key, *aggregates])
    # Registered grouping ties are deterministic; NULL sorts first in ASC.
    grouping_fields = (["time_bucket"] if grain != "none" else []) + dimensions
    def ascending(row, keys):
        return tuple((row[fields.index(key)] is not None, row[fields.index(key)]) for key in keys)
    result.sort(key=lambda row: ascending(row, grouping_fields))
    order = spec.get("order_by")
    if order:
        result.sort(key=lambda row: ascending(row, [order]), reverse=spec.get("descending", False))
    limit = spec.get("limit", 100)
    truncated = len(result) > limit
    result = result[:limit]
    chart = spec.get("chart", "table")
    visualization = {"kind": chart}
    if chart in {"bar", "line"}:
        visualization.update(x=fields[0], y=metric_ids[0])
    return {"kind": "report", "fields": fields,
            "types": [("date" if field == "time_bucket" else "integer" if field in {"jobs_count", "borrowings"}
                       else "decimal" if field in metrics else "text") for field in fields],
            "rows": [[str(value) if isinstance(value, Decimal) else value for value in row] for row in result],
            "chart": chart, "visualization": visualization, "truncated": truncated, "bounds": bounds}
