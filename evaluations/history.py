"""Allowlisted local inventory of the existing private Rahtal evidence bundle.

This imports exact questions into memory to compare provenance, but returns only
IDs, hashes, booleans and fixed classifications. It never runs a historical
script or substitutes these recorded results for a fresh live evaluation.
"""

from collections import Counter
from hashlib import sha256
import json
from pathlib import Path


CLASSIFICATIONS = {"PASS", "UNSUPPORTED", "FAIL", "PARTIAL", "BLOCKED", "UNVERIFIED"}


def inventory(directory: Path):
    def read(name):
        return json.loads((directory / name).read_text(encoding="utf-8-sig"))
    questions = read("questions.json")
    verification = read("verification_results.json")
    expected = read("expected_results.json")
    summaries = read("pipeline_summary.json")
    if not isinstance(questions, list) or not questions:
        raise ValueError("Missing question corpus")
    by_id = {row["test"]: row for row in verification}
    summary_by_id = {row["test"]: row for row in summaries}
    ids = [row["test"] for row in questions]
    if (len(set(ids)) != len(ids) or set(ids) != set(by_id) or set(ids) != set(summary_by_id)
            or len(verification) != len(ids) or len(summaries) != len(ids)):
        raise ValueError("Historical case identities disagree")
    cases = []
    for question in questions:
        number = question["test"]
        if type(number) is not int or not 1 <= number <= 99:
            raise ValueError("Invalid historical case ID")
        record, summary = by_id[number], summary_by_id[number]
        expectation = expected[str(number)]
        classification = record["status_classification"]
        if classification not in CLASSIFICATIONS or not isinstance(question["question"], str):
            raise ValueError("Unknown historical classification")
        reply_name = f"test_{number:02d}_reply.json"
        reply = read(reply_name)
        report = reply.get("report")
        exact_question = question["question"] == record["question"] == summary["question"]
        statuses = reply["status"] == record["status"] == summary["status"]
        report_consistent = bool(report) == record["report_produced"] == summary["report_produced"]
        if report:
            report_consistent = report_consistent and len(report["rows"]) == record["row_count"]
        claimed_report = classification == "PASS"
        evidence_complete = all(record.get(key) is True for key in (
            "numeric_match", "requested_complete", "date_match", "source_stable", "independent_reference_complete"))
        bounds_match = bool(report) and [report["provenance"]["period_start"],
                                        report["provenance"]["period_end_exclusive"]] == expectation["bounds"]
        consistent = exact_question and statuses and report_consistent and (
            not claimed_report or evidence_complete and bounds_match and reply["status"] == "report_ready")
        if classification == "UNSUPPORTED":
            consistent = consistent and reply["status"] == "unsupported" and report is None
        cases.append({
            "id": f"rahtal_{number:02d}", "recorded_classification": classification,
            "exact_question_matches": exact_question,
            "question_sha256": sha256(question["question"].encode("utf-8")).hexdigest(),
            "expected_result_present": isinstance(expectation.get("rows"), list),
            "reply_sha256": sha256((directory / reply_name).read_bytes()).hexdigest(),
            "recorded_correctness_checks_complete": evidence_complete if claimed_report else None,
            "bounds_match": bounds_match if claimed_report else None,
            "interpretation_capture_present": (directory / f"test_{number:02d}_interpretations.json").is_file(),
            "query_capture_present": (directory / f"test_{number:02d}_queries.json").is_file(),
            "evidence_consistent": bool(consistent),
        })
    return {
        "schema_version": 1, "mode": "historical_inventory",
        "live_model_status": "not_executed",
        "data_correctness_reexecuted": False,
        "evidence_consistent": all(row["evidence_consistent"] for row in cases),
        "summary": {"cases": len(cases), "recorded_outcomes": dict(sorted(Counter(
            row["recorded_classification"] for row in cases).items()))},
        "cases": cases,
    }
