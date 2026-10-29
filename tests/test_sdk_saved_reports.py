"""Saved report definitions: zero model calls, dynamic dates, current policies."""
from dataclasses import replace
from datetime import date

import pytest

from sageql.sdk import (
    ActorContext, Interpretation, PeriodSelection, ReportSpec, SageQL, SDKError,
    SQLiteSavedReportStore, UserFilter,
)
from sageql.sdk.saved import MAX_SAVED_PER_OWNER, InMemorySavedReportStore
from test_sdk_intent import ACTOR, TODAY, Adapter, catalog, database, scope  # noqa: F401

MONTHLY = ReportSpec("activities", ("hours",), ("unit",), period=PeriodSelection("last_month"))
OTHER = ActorContext("someone-else", "7")


class Provider:
    """Counts interpretations; saved runs must never call it."""

    def __init__(self, spec):
        self.spec, self.calls = spec, 0

    def interpret(self, messages, current, catalog, today):
        self.calls += 1
        return Interpretation("ready", self.spec)


def build(database, spec=MONTHLY, **options):
    provider = Provider(spec)
    sdk = SageQL(catalog=catalog(), database=Adapter(database), provider=provider,
                 policy=options.pop("policy", lambda _: scope()), clock=options.pop("clock", lambda: TODAY),
                 execution=options.pop("execution", "validated"), **options)
    session = sdk.create_session(ACTOR)
    reply = sdk.submit(session.session_id, "ساعات فعالیت ماه گذشته به تفکیک واحد", ACTOR, "r1", 0)
    assert reply.status == "report_ready"
    return sdk, provider, session.session_id, reply.report


def test_saved_report_reruns_with_fresh_data_and_no_model_call(database):
    sdk, provider, session_id, report = build(database)
    saved = sdk.save_report(session_id, report.id, ACTOR, "  ساعات ماهانه  ")
    assert saved["name"] == "ساعات ماهانه" and saved["period"]["kind"] == "last_month"
    reply = sdk.run_saved_report(saved["id"], ACTOR)
    assert reply.status == "report_ready" and reply.report.rows == report.rows
    assert reply.report.provenance["saved_report_id"] == saved["id"]
    assert provider.calls == 1
    assert len(sdk.database.calls) == 2


def test_relative_period_moves_with_the_business_date(database):
    clock = {"today": TODAY}
    sdk, _, session_id, _ = build(database, clock=lambda: clock["today"])
    saved = sdk.save_report(session_id, sdk.get_session(session_id, ACTOR)["last_report_id"], ACTOR, "Monthly")
    clock["today"] = date(2026, 11, 8)
    reply = sdk.run_saved_report(saved["id"], ACTOR)
    assert reply.report.provenance["period_start"] == "2026-10-01"
    assert reply.report.provenance["period_end_exclusive"] == "2026-11-01"


def test_fixed_dates_can_become_dynamic_on_save_or_be_overridden_per_run(database):
    fixed = replace(MONTHLY, period=PeriodSelection("range", "2026-09-01", "2026-10-01"))
    sdk, _, session_id, report = build(database, spec=fixed)
    kept = sdk.save_report(session_id, report.id, ACTOR, "September")
    dynamic = sdk.save_report(session_id, report.id, ACTOR, "Previous month",
                              period=PeriodSelection("last_month"))
    assert kept["period"]["kind"] == "range" and dynamic["period"]["kind"] == "last_month"
    reply = sdk.run_saved_report(kept["id"], ACTOR, period=PeriodSelection("this_month"))
    assert reply.report.provenance["period_start"] == "2026-10-01"


def test_filter_override_replaces_saved_filters(database):
    sdk, _, session_id, report = build(database)
    saved = sdk.save_report(session_id, report.id, ACTOR, "By unit")
    assert {row[0] for row in report.rows} == {"A", "B"}
    reply = sdk.run_saved_report(saved["id"], ACTOR, filters=())
    assert reply.status == "report_ready"
    bad = sdk.run_saved_report(saved["id"], ACTOR, filters=[UserFilter("x", "eq", ("y",))])
    assert bad.status == "blocked" and bad.error["code"] == "invalid_input"


def test_saved_reports_are_owner_scoped(database):
    sdk, _, session_id, report = build(database)
    saved = sdk.save_report(session_id, report.id, ACTOR, "Mine")
    assert sdk.list_saved_reports(OTHER) == []
    denied = sdk.run_saved_report(saved["id"], OTHER)
    assert denied.status == "blocked" and denied.error["code"] == "access_denied"
    with pytest.raises(SDKError):
        sdk.delete_saved_report(saved["id"], OTHER)
    sdk.delete_saved_report(saved["id"], ACTOR)
    assert sdk.list_saved_reports(ACTOR) == []


def test_current_policy_and_execution_opt_in_apply_on_every_run(database):
    state = {"allowed": True}

    def policy(actor):
        if not state["allowed"]:
            raise SDKError("access_denied", "Revoked.")
        return scope()

    sdk, _, session_id, report = build(database, policy=policy)
    saved = sdk.save_report(session_id, report.id, ACTOR, "Policy")
    state["allowed"] = False
    assert sdk.run_saved_report(saved["id"], ACTOR).error["code"] == "access_denied"
    state["allowed"] = True
    sdk.execution = "disabled"
    assert sdk.run_saved_report(saved["id"], ACTOR).error["code"] == "execution_disabled"


def test_comparison_period_override_and_bad_names_are_rejected(database):
    comparison = replace(MONTHLY, dimension_ids=(), period=PeriodSelection("range", "2026-09-01", "2026-10-01"),
                         comparison=PeriodSelection("range", "2026-08-01", "2026-09-01"))
    sdk, _, session_id, report = build(database, spec=comparison)
    with pytest.raises(SDKError):
        sdk.save_report(session_id, report.id, ACTOR, "x", period=PeriodSelection("last_month"))
    with pytest.raises(SDKError):
        sdk.save_report(session_id, report.id, ACTOR, "   ")
    saved = sdk.save_report(session_id, report.id, ACTOR, "Comparison")
    assert saved["has_comparison"]
    assert sdk.run_saved_report(saved["id"], ACTOR, period=PeriodSelection("last_month")).error["code"] == "invalid_input"


def test_sqlite_store_persists_across_instances(database, tmp_path):
    path = tmp_path / "saved.sqlite"
    sdk, provider, session_id, report = build(database, saved_reports=SQLiteSavedReportStore(path))
    saved = sdk.save_report(session_id, report.id, ACTOR, "Persistent")
    reopened = SageQL(catalog=catalog(), database=Adapter(database), provider=provider,
                      policy=lambda _: scope(), clock=lambda: TODAY, execution="validated",
                      saved_reports=SQLiteSavedReportStore(path))
    assert [item["id"] for item in reopened.list_saved_reports(ACTOR)] == [saved["id"]]
    assert reopened.run_saved_report(saved["id"], ACTOR).report.rows == report.rows
    assert provider.calls == 1


def test_owner_limit_is_enforced():
    store = InMemorySavedReportStore()
    for index in range(MAX_SAVED_PER_OWNER):
        store.save({"id": str(index), "owner": ["a", "t"], "schema_version": 1})
    with pytest.raises(SDKError) as error:
        store.save({"id": "extra", "owner": ["a", "t"], "schema_version": 1})
    assert error.value.code == "saved_report_limit"
    store.save({"id": "other", "owner": ["b", "t"], "schema_version": 1})
