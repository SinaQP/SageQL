"""An installed-package embedding smoke test with synthetic data and no network."""

from contextlib import closing
from dataclasses import replace
from datetime import date
import json
from pathlib import Path
import sqlite3
import sys
from tempfile import TemporaryDirectory

from sageql import Column, SageQL, Table
from sageql.sdk import (
    AccessScope, ActorContext, DatasetAccess, DatasetDefinition, DimensionDefinition,
    Interpretation, MetricDefinition, PeriodSelection, ReportingCatalog, ReportSpec,
    RowPolicy, SQLiteAdapter, SQLiteSessionStore, TimeDefinition,
)


class DemoProvider:
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


def main():
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

    def policy(actor):
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
        engine = SageQL(catalog=catalog, database=SQLiteAdapter(data), provider=DemoProvider(),
                        policy=policy, sessions=SQLiteSessionStore(Path(directory) / "sessions.sqlite"),
                        clock=lambda: date(2026, 10, 5), execution="validated")
        session = engine.create_session(actor)
        question = engine.submit(session.session_id, "ساعات فعالیت روزانه در سپتامبر", actor, "first", 0)
        daily = engine.submit(session.session_id, "۲۰۲۶", actor, "year", question.revision)
        grouped = engine.submit(session.session_id, "به تفکیک کارمند نمایش بده", actor, "group", daily.revision)
        if question.status != "needs_clarification" or daily.status != "report_ready" or grouped.status != "report_ready":
            raise RuntimeError("Embedding smoke test did not produce its expected reports")
        if grouped.to_dict()["report"]["rows"] != [["Alex", "7"], ["Sam", "2.5"]]:
            raise RuntimeError("Embedding smoke test totals did not match")
        if callable(getattr(sys.stdout, "reconfigure", None)):
            sys.stdout.reconfigure(encoding="utf-8")
        print(json.dumps(grouped.to_dict(), indent=2, allow_nan=False, ensure_ascii=False))


if __name__ == "__main__":
    main()
