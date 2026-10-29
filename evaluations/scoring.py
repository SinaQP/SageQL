"""Independent outcome classification, with explicit metric denominators."""

from collections import Counter
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from statistics import median
from typing import Any


@dataclass(frozen=True)
class Assessment:
    outcome: str
    checks: dict[str, bool]


def rows_match(fields, actual, expected):
    """Compare exact numeric values without depending on decimal string scale."""
    def scalar(field, left, right):
        if left is None or right is None:
            return left is right
        if field["type"] in {"decimal", "number", "integer"}:
            if isinstance(left, bool) or isinstance(right, bool):
                return False
            try:
                a, b = Decimal(str(left)), Decimal(str(right))
                return a.is_finite() and b.is_finite() and a == b
            except InvalidOperation:
                return False
        return type(left) is type(right) and left == right
    return len(actual) == len(expected) and all(
        len(a) == len(b) == len(fields) and all(scalar(f, x, y) for f, x, y in zip(fields, a, b))
        for a, b in zip(actual, expected))


def assess(expected: dict[str, Any], reply: dict[str, Any], *,
           spec_matches: bool = True, invariants: bool = True) -> Assessment:
    """A successful status alone never establishes a correct, complete report.

    Expectations are fixture-owned, never taken from a reviewer judgment. Rows
    are compared in order using the public JSON scalar contract. Explicit top-N
    truncation is allowed only when the expectation declares it.
    """
    goal, status = expected["kind"], reply["status"]
    report = reply.get("report")
    checks = {"invariants": invariants}
    if report is not None and status != "report_ready":
        return Assessment("incomplete", {**checks, "atomic_response": False})
    if status == "report_ready":
        if not isinstance(report, dict):
            return Assessment("incomplete", {**checks, "report_present": False})
        if goal != "report":
            return Assessment("unexpected_report", checks)
        checks.update(
            specification=spec_matches,
            fields=[field["id"] for field in report["fields"]] == expected["fields"],
            types=[field["type"] for field in report["fields"]] == expected["types"],
            rows=rows_match(report["fields"], report["rows"], expected["rows"]),
            truncation=report["truncated"] == expected.get("truncated", False),
            presentation=report["visualization"]["kind"] == expected["chart"],
            axes=report["visualization"] == expected.get("visualization", {"kind": expected["chart"]}),
            response=bool(reply["assistant"]["text"].strip()) and reply.get("error") is None,
        )
        if (set(expected["fields"]) - {f["id"] for f in report["fields"]}
                or len(report["rows"]) < len(expected["rows"]) or not checks["truncation"]):
            return Assessment("incomplete", checks)
        return Assessment("correct_report" if all(checks.values()) else "semantic_error", checks)
    if status == "needs_clarification":
        checks["clarification"] = bool(reply.get("clarification")) and (
            expected.get("question_contains", "").casefold()
            in reply["clarification"].casefold())
        return Assessment("correct_clarification" if goal == "clarification" and all(checks.values())
                          else "incorrect_rejection", checks)
    if status == "unsupported":
        checks["explanation"] = bool(reply["assistant"]["text"].strip())
        return Assessment("correct_unsupported" if goal == "unsupported" and all(checks.values())
                          else "incorrect_rejection", checks)
    error = reply.get("error") or {}
    if error.get("code") == "access_denied":
        return Assessment("correct_denial" if goal == "denial" and invariants
                          else "incorrect_rejection", checks)
    # Safe blocking of a deliberately invalid candidate is distinct from access
    # denial and from failure to perform an ordinary supported request.
    if goal == "blocked" and status == "blocked" and error.get("code") == expected["error_code"]:
        return Assessment("correct_block" if invariants else "semantic_error", checks)
    if status == "failed":
        return Assessment("operational_failure", checks)
    return Assessment("incorrect_rejection", checks)


def summarize(results: list[dict[str, Any]]) -> dict[str, Any]:
    """Rates are fractions with denominators; an empty population is unmeasured."""
    def rate(population, predicate):
        selected = [item for item in results if population(item)]
        return {"numerator": sum(bool(predicate(item)) for item in selected),
                "denominator": len(selected),
                "value": (sum(bool(predicate(item)) for item in selected) / len(selected)
                          if selected else None)}

    return {
        "cases": len(results),
        "outcomes": dict(sorted(Counter(item["outcome"] for item in results).items())),
        "supported_completion": rate(lambda x: x["goal"] == "report",
                                     lambda x: x["outcome"] == "correct_report"),
        "semantic_correctness": rate(lambda x: x["status"] == "report_ready",
                                     lambda x: x["outcome"] == "correct_report"),
        "report_completeness": rate(lambda x: x["goal"] == "report",
                                    lambda x: x["outcome"] == "correct_report"),
        "clarification_precision": rate(lambda x: x["status"] == "needs_clarification",
                                        lambda x: x["outcome"] == "correct_clarification"),
        "unsupported_classification_accuracy": rate(
            lambda x: x["goal"] in {"report", "clarification", "unsupported"},
            lambda x: (x["status"] == "unsupported") == (x["goal"] == "unsupported")),
        "unauthorized_prevention": rate(lambda x: x["goal"] == "denial",
                                        lambda x: x["outcome"] == "correct_denial" and x["database_calls"] == 0),
        "recovery_effectiveness": rate(lambda x: x["recovery_expected"],
                                      lambda x: x["outcome"] == "correct_report"),
        "new_regressions": sum(not x["meets_baseline"] for x in results),
        "known_failures": sum(bool(x["known_issue"]) and x["outcome"] == x["baseline_outcome"] for x in results),
        "model_calls": sum(x["model_calls"] for x in results),
        "model_calls_per_request": (sum(x["model_calls"] for x in results) /
                                    sum(len(x["turns"]) for x in results)) if results else None,
        "requests": sum(len(x["turns"]) for x in results),
        "database_calls": sum(x["database_calls"] for x in results),
        "recovery_attempts": {kind: sum(x["recovery_attempts"][kind] for x in results)
                              for kind in ("planning_revisions", "structured_repairs", "intent_reconsiderations")},
        "latency_ms": {"total": round(sum(x["elapsed_ms"] for x in results), 3),
                       "median": median(x["elapsed_ms"] for x in results) if results else None},
    }
