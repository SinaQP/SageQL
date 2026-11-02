"""Offline SDK demo: a Persian three-turn conversation on synthetic data, no network.

`sageql demo` runs it. The interpreter is scripted, so no model or API key is
involved; everything after interpretation (policy, compilation, read-only
execution, sessions) is the real engine.
"""

import argparse
from contextlib import closing
from dataclasses import replace
from datetime import date
import json
from pathlib import Path
import sqlite3
import sys
from tempfile import TemporaryDirectory

from sageql.schema import Column, Table
from sageql.sdk import (
    AccessScope, ActorContext, DatasetAccess, DatasetDefinition, DimensionDefinition,
    Interpretation, MetricDefinition, PeriodSelection, ReportingCatalog, ReportSpec,
    RowPolicy, SageQL, SQLiteAdapter, SQLiteSessionStore, TimeDefinition,
)
from sageql.sdk.adapters import compile_report

TURNS = ("ساعات فعالیت روزانه در سپتامبر", "۲۰۲۶", "به تفکیک کارمند نمایش بده")
DOCS = "https://github.com/SinaQP/SageQL/blob/main/docs/SDK.md"


class DemoProvider:
    """Stands in for the model: returns typed report specs, never SQL."""

    def interpret(self, messages, current_spec, catalog, today):
        if current_spec is not None:
            return Interpretation("ready", replace(current_spec, dimension_ids=("employee",),
                                                    time_grain="none", chart="bar"))
        if not any(year in messages[-1].content for year in ("2026", "۲۰۲۶", "٢٠٢٦")):
            return Interpretation("needs_clarification", question="کدام سال میلادی را می‌خواهید؟")
        return Interpretation("ready", ReportSpec(
            "activities", ("activity_hours",), period=PeriodSelection("month", year=2026, month=9),
            time_grain="day", chart="line",
        ))


class CapturingAdapter:
    """The real SQLite adapter, keeping each compiled query so the demo can show it."""

    def __init__(self, path):
        self.delegate, self.queries = SQLiteAdapter(path), []

    def execute(self, report, limits, *, cancel=None):
        self.queries.append(compile_report(report, limits, dialect="sqlite"))
        return self.delegate.execute(report, limits, cancel=cancel)


def run_demo():
    """Run the three turns and return (replies, compiled queries)."""
    table = Table("activities")
    catalog = ReportingCatalog((DatasetDefinition(
        "activities", "فعالیت‌ها", table,
        tuple(Column(table.key, name, kind) for name, kind in (
            ("tenant_id", "int"), ("employee", "text"), ("activity_date", "date"), ("hours", "decimal"),
        )),
        metrics=(MetricDefinition("activity_hours", "ساعات فعالیت", "sum", "hours", "ساعت"),),
        dimensions=(DimensionDefinition("employee", "کارمند", "employee"),),
        time=TimeDefinition("activity_date"),
    ),))

    def policy(actor):  # Every query is bound to the caller's tenant.
        return AccessScope((DatasetAccess("activities", policies=(
            RowPolicy("tenant_id", "eq", (int(actor.tenant_id),)),
        )),))

    actor = ActorContext("demo-user", "1")  # Obtained by the host's authentication layer.
    with TemporaryDirectory(prefix="sageql-sdk-") as directory:
        data = Path(directory) / "data.sqlite"
        with closing(sqlite3.connect(data)) as connection, connection:
            connection.execute("CREATE TABLE activities (tenant_id INTEGER, employee TEXT, activity_date DATE, hours DECIMAL)")
            connection.executemany("INSERT INTO activities VALUES (?, ?, ?, ?)", [
                (1, "Alex", "2026-09-01", 4), (1, "Sam", "2026-09-01", 2.5),
                (1, "Alex", "2026-09-02", 3), (2, "Other tenant", "2026-09-01", 999),
            ])
        database = CapturingAdapter(data)
        engine = SageQL(catalog=catalog, database=database, provider=DemoProvider(),
                        policy=policy, sessions=SQLiteSessionStore(Path(directory) / "sessions.sqlite"),
                        clock=lambda: date(2026, 10, 5), execution="validated")
        session = engine.create_session(actor)
        replies, revision = [], session.revision
        for index, message in enumerate(TURNS):
            reply = engine.submit(session.session_id, message, actor, f"turn-{index}", revision)
            replies.append(reply)
            revision = reply.revision
    if [reply.status for reply in replies] != ["needs_clarification", "report_ready", "report_ready"]:
        raise RuntimeError("The SDK demo did not produce its expected replies")
    if replies[-1].to_dict()["report"]["rows"] != [["Alex", "7"], ["Sam", "2.5"]]:
        raise RuntimeError("The SDK demo totals did not match")
    return replies, database.queries


def _describe(reply):
    data = reply.to_dict()
    if data["status"] == "needs_clarification":
        return [f"[needs clarification] {data['assistant']['text']}"]
    report = data["report"]
    lines = [f"[report ready] {data['assistant']['text']}"]
    headers = [f"{field['label']} ({field['unit']})" if field["unit"] else field["label"]
               for field in report["fields"]]
    rows = [[str(value) for value in row] for row in report["rows"]]
    shown = rows[:5]
    widths = [max(len(cell) for cell in column) for column in zip(headers, *shown)]
    for cells in (headers, *shown):
        lines.append(" | ".join(cell.ljust(width) for cell, width in zip(cells, widths)).rstrip())
    if len(rows) > len(shown):
        lines.append(f"... {len(rows) - len(shown)} more rows")
    return lines


def main(argv=None):
    parser = argparse.ArgumentParser(prog="sageql demo", description=__doc__.splitlines()[0])
    parser.add_argument("--json", action="store_true", help="print the final reply as JSON")
    args = parser.parse_args(argv)
    if callable(getattr(sys.stdout, "reconfigure", None)):
        sys.stdout.reconfigure(encoding="utf-8")
    replies, queries = run_demo()
    if args.json:
        print(json.dumps(replies[-1].to_dict(), indent=2, allow_nan=False, ensure_ascii=False))
        return 0
    print("SageQL offline demo: synthetic data and a scripted interpreter; no network or API key.\n")
    for message, reply in zip(TURNS, replies):
        print(f"You:    {message}")
        for number, line in enumerate(_describe(reply)):
            print(f"{'SageQL: ' if number == 0 else '        '}{line}")
        print()
    final = queries[-1]
    print("SQL compiled by SageQL for the last report (the interpreter only chose concepts):")
    print("\n".join(f"  {line}" for line in final.sql.splitlines()))
    print(f"  parameters: {[str(value) for value in final.parameters]}")
    print("\nTenant 2's 999 hours never appear: the actor's row policy is a bound parameter in every query.")
    print(f"Full reply JSON: sageql demo --json   Embedding guide: {DOCS}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
