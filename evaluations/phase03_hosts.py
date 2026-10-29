"""Third independent synthetic host, using only existing registered operations."""
from contextlib import closing
from datetime import date
import json
from pathlib import Path
import sqlite3

from examples import multi_domain
from sageql import Column, Table
from sageql.sdk import (
    AccessScope, ActorContext, DatasetAccess, DatasetDefinition, DimensionDefinition,
    FilterDefinition, MetricDefinition, ReportingCatalog, RowPolicy, SDKError, TimeDefinition,
)

ROOT = Path(__file__).with_name("phase03")
TODAY = date(2026, 10, 24)
ACTOR = ActorContext("synthetic-evaluator", attributes={"org": "blue", "store": "north", "branch": "N"})


def workshop_catalog():
    table = Table("workshop_jobs")
    return ReportingCatalog((DatasetDefinition("jobs", "Workshop jobs", table,
        tuple(Column(table.key, name, kind) for name, kind in (
            ("org", "nvarchar(40)"), ("voided", "bit"), ("completed", "date"),
            ("service", "nvarchar(80)"), ("channel", "nvarchar(40)"),
            ("technician", "nvarchar(40)"), ("fee", "decimal"), ("minutes", "int"))),
        metrics=(MetricDefinition("billed", "Billed amount", "sum", "fee", "USD",
                                  selection_terms=("fees", "دستمزد")),
                 MetricDefinition("jobs_count", "Completed jobs", "count_rows", unit="jobs",
                                  selection_terms=("job count", "تعداد کارها")),
                 MetricDefinition("minutes_total", "Work minutes", "sum", "minutes", "minutes",
                                  selection_terms=("دقایق کار",)),
                 MetricDefinition("minutes_mean", "Minutes per job", "average", "minutes", "minutes",
                                  selection_terms=("average job duration",))),
        dimensions=tuple(DimensionDefinition(key, label, key) for key, label in (
            ("service", "Service"), ("channel", "Channel"), ("technician", "Technician"))),
        filters=tuple(FilterDefinition(key + "_filter", label, key) for key, label in (
            ("service", "Service"), ("channel", "Channel"), ("technician", "Technician"))),
        time=TimeDefinition("completed"), default_metric_ids=("billed",),
        description="One completed workshop job. Fees are billed amounts, not profit. No cost or payroll relationship is registered."),))


def workshop_policy(actor):
    org = actor.attributes.get("org")
    if org != "blue":
        raise SDKError("access_denied", "A trusted workshop organization is required.")
    return AccessScope((DatasetAccess("jobs", policies=(RowPolicy("org", "eq", (org,)),
                                                       RowPolicy("voided", "eq", (False,)))),), version="workshop-v1")


def create_workshop_data(path):
    records = json.loads((ROOT / "records.json").read_text(encoding="utf-8"))
    with closing(sqlite3.connect(path)) as connection, connection:
        connection.execute("CREATE TABLE workshop_jobs (org TEXT, voided BIT, completed DATE, service TEXT, channel TEXT, technician TEXT, fee DECIMAL, minutes INT)")
        connection.executemany("INSERT INTO workshop_jobs VALUES (?, ?, ?, ?, ?, ?, ?, ?)", records["rows"])


def host(domain):
    if domain == "workshop":
        return workshop_catalog(), workshop_policy, create_workshop_data
    scenario = next(item for item in multi_domain.scenarios() if item.name == domain)
    return scenario.catalog, scenario.policy, scenario.create_data
