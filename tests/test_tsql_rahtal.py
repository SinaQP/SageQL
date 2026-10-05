"""Offline checks for the Rahtal T-SQL pilot and execution guard."""

import argparse
import json
import sys
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

import pytest

from sageql.context import ContextResolution, ResolvedContext
from sageql.discovery import QuerySpace
from sageql.planning import (PlanCandidates, PlanProposal, PlannedJoin, PlannedMeasure,
                             PlannedFilter, ProposedFilter, ProposedJoin, ProposedMeasure, QueryPlan)
from sageql.tsql import TSQLReportError, execute_tsql_report, render_tsql_report, validate_tsql_report
from sageql.understanding import RequestAssessment
from sageql_rahtal.catalog import daily_performance_catalog, policy_columns
from sageql_rahtal.run import _PilotPlanningProvider, _load_local_config, _resolve_options, run


def _cli_args(config: Path, **overrides):
    values = dict(config=str(config), question=None, env=None, reports=None,
                  period_start=None, period_end=None, comparison_start=None,
                  comparison_end=None, max_rows=None, timeout=None, no_execute=None)
    values.update(overrides)
    return argparse.Namespace(**values)


def test_local_config_supplies_question_mode_paths_and_limits(tmp_path):
    config_path = tmp_path / "local_config.py"
    config_path.write_text(
        'QUESTION = "Daily activity hours"\nRUN_MODE = "execute"\n'
        'ENV_FILE = "private.env"\nREPORTS_DIR = "my_reports"\n'
        'MAX_ROWS = 25\nTIMEOUT_SECONDS = 7\nLLM_TIMEOUT_SECONDS = 45\n', encoding="utf-8",
    )
    config = _load_local_config(config_path)
    options = _resolve_options(_cli_args(config_path), config, config_path)
    assert options.question_text == "Daily activity hours"
    assert options.no_execute is False
    assert options.env == tmp_path / "private.env"
    assert options.reports == tmp_path / "my_reports"
    assert (options.max_rows, options.timeout) == (25, 7)
    assert options.llm_timeout == 45

    question_file = tmp_path / "another.txt"
    question_file.write_text("Another question", encoding="utf-8")
    overridden = _resolve_options(_cli_args(config_path, question=str(question_file), no_execute=True,
                                            max_rows=5), config, config_path)
    assert overridden.question_text is None
    assert overridden.question_path == question_file
    assert overridden.no_execute is True
    assert overridden.max_rows == 5


def test_invalid_local_config_saves_a_failure_report_without_model_call(tmp_path):
    config_path = tmp_path / "local_config.py"
    config_path.write_text('QUESTION = "test"\nRUN_MODE = "write"\n', encoding="utf-8")
    reports = tmp_path / "reports"
    assert run(_cli_args(config_path, reports=str(reports))) == 1
    report = next(reports.glob("*.json"))
    assert '"stage": "Local config"' in report.read_text(encoding="utf-8")


def test_local_config_rejects_half_a_date_range(tmp_path):
    config_path = tmp_path / "local_config.py"
    config_path.write_text('QUESTION = "Daily hours"\nPERIOD_START = "2026-01-01"\n',
                           encoding="utf-8")
    with pytest.raises(ValueError, match="both be set"):
        _resolve_options(_cli_args(config_path), _load_local_config(config_path), config_path)


def test_local_config_rejects_invalid_model_timeout(tmp_path):
    config_path = tmp_path / "local_config.py"
    config_path.write_text('QUESTION = "Daily hours"\nLLM_TIMEOUT_SECONDS = 0\n',
                           encoding="utf-8")
    with pytest.raises(ValueError, match="LLM_TIMEOUT_SECONDS"):
        _load_local_config(config_path)


def test_runner_continues_same_conversation_through_execution_after_multiple_clarifications(
    tmp_path, monkeypatch,
):
    import sageql_rahtal.run as runner

    class Provider:
        def __init__(self):
            self.understanding_histories = []
            self.context_histories = []

        def assess(self, messages):
            self.understanding_histories.append(tuple(messages))
            if len(self.understanding_histories) == 1:
                return RequestAssessment(False, "", "Which measure?")
            if len(self.understanding_histories) == 2:
                return RequestAssessment(False, "", "Which users?")
            return RequestAssessment(True, "Total activity hours for all users", "")

        def resolve_context(self, messages, understanding):
            assert understanding == "Total activity hours for all users"
            self.context_histories.append(tuple(messages))
            partial = ResolvedContext("", ("activities",), ("activity hours",), (), "")
            dated = replace(partial, time_period="all available data")
            if len(self.context_histories) == 1:
                return ContextResolution(False, partial, "Which period?")
            if len(self.context_histories) == 2:
                return ContextResolution(False, dated, "How should results be grouped?")
            return ContextResolution(True, dated, "")

        def propose_query_plan(self, understanding, context, candidates):
            assert context.time_period == "all available data"
            amount_id = next(key for key, column in candidates.columns.items()
                             if column.key == "dbo.functionality_activities.time")
            return PlanProposal("t0", (), "", "none", (),
                                (ProposedMeasure("activity hours", "sum", amount_id),), ())

    provider = Provider()
    monkeypatch.setitem(sys.modules, "openai", SimpleNamespace(OpenAI=lambda **kwargs: object()))
    monkeypatch.setattr(runner, "OpenAIChatProvider", lambda *args, **kwargs: provider)
    monkeypatch.setattr(runner, "_load_settings", lambda path: {
        "RAHTAL_DB_SERVER": "test-host", "RAHTAL_DB_DATABASE": "test-db",
        "RAHTAL_DB_USERNAME": "test-user", "RAHTAL_DB_PASSWORD": "test-password",
        "RAHTAL_DB_DRIVER": "test-driver", "RAHTAL_DB_SCHEMA": "dbo",
        "RAHTAL_LLM_API_KEY": "test-key", "RAHTAL_LLM_BASE_URL": "https://example.test",
        "RAHTAL_LLM_MODEL": "test-model",
    })
    monkeypatch.setattr(runner, "_check_live_catalog", lambda settings, catalog: catalog)
    monkeypatch.setattr(runner, "discover_query_space",
                        lambda catalog, provider, understanding, context: QuerySpace(
                            catalog.tables, catalog.columns, catalog.relations, catalog.definitions))
    monkeypatch.setattr(runner, "_connect", lambda settings: _Connection())
    config_path = tmp_path / "local_config.py"
    config_path.write_text('QUESTION = "Show daily performance"\nRUN_MODE = "execute"\n',
                           encoding="utf-8")
    replies = iter(("", "activity hours", "all users", "all available data", "no grouping"))
    prompts = []

    def answer_input(prompt):
        prompts.append(prompt)
        return next(replies)

    reports = tmp_path / "reports"
    assert run(_cli_args(config_path, reports=str(reports)), answer_input) == 0

    report = json.loads(next(reports.glob("*.json")).read_text(encoding="utf-8"))
    assert report["status"] == "completed"
    assert report["row_count"] == 1
    assert [entry["stage"] for entry in report["stages"]][-4:] == [
        "6. Query planning", "7. SQL generation", "8. Validation and safety", "9. Query execution"
    ]
    assert len(provider.understanding_histories) == 3
    assert len(provider.context_histories) == 3
    assert [message.content for message in provider.understanding_histories[-1]
            if message.role == "user"] == [
        "Show daily performance", "activity hours", "all users"
    ]
    assert [message.content for message in provider.context_histories[-1]
            if message.role == "user"] == [
        "Show daily performance", "activity hours", "all users", "all available data", "no grouping"
    ]
    assert len(prompts) == 5
    assert sum(stage["stage"] == "3. Clarification answer" for stage in report["stages"]) == 2
    assert [stage["details"]["context_so_far"]["time_period"] for stage in report["stages"]
            if stage["stage"] == "3. Clarification answer"] == ["", "all available data"]


def test_runner_keeps_pending_clarification_when_input_closes(tmp_path, monkeypatch):
    import sageql_rahtal.run as runner

    class Provider:
        def assess(self, messages):
            return RequestAssessment(False, "", "Which measure?")

    monkeypatch.setitem(sys.modules, "openai", SimpleNamespace(OpenAI=lambda **kwargs: object()))
    monkeypatch.setattr(runner, "OpenAIChatProvider", lambda *args, **kwargs: Provider())
    monkeypatch.setattr(runner, "_load_settings", lambda path: {
        "RAHTAL_DB_SERVER": "test-host", "RAHTAL_DB_DATABASE": "test-db",
        "RAHTAL_DB_DRIVER": "test-driver", "RAHTAL_DB_SCHEMA": "dbo",
        "RAHTAL_LLM_API_KEY": "test-key", "RAHTAL_LLM_BASE_URL": "https://example.test",
        "RAHTAL_LLM_MODEL": "test-model",
    })
    config_path = tmp_path / "local_config.py"
    config_path.write_text('QUESTION = "Show performance"\n', encoding="utf-8")

    def closed_input(prompt):
        raise EOFError

    reports = tmp_path / "reports"
    assert run(_cli_args(config_path, reports=str(reports)), closed_input) == 2
    report = json.loads(next(reports.glob("*.json")).read_text(encoding="utf-8"))
    assert report["status"] == "needs_clarification"
    assert report["error"] == "Which measure?"


def _fixture():
    catalog = daily_performance_catalog()
    space = QuerySpace(catalog.tables, catalog.columns, catalog.relations, catalog.definitions)
    tables = {table.key: table for table in catalog.tables}
    columns = {column.key: column for column in catalog.columns}
    context = ResolvedContext("all available data", (), ("activity hours",), (), "")
    plan = QueryPlan(
        tables["dbo.functionality_activities"],
        (PlannedJoin(catalog.relations[0], tables["dbo.authentication_user"], "left"),
         PlannedJoin(catalog.relations[1], tables["dbo.persons_person"], "left")),
        None, context.time_period, "none",
        (columns["dbo.persons_person.first_name"],),
        (PlannedMeasure("activity hours", "sum", columns["dbo.functionality_activities.time"]),),
        (), "", "Total activity hours by first name across all available data",
    )
    return plan, context, space


def test_policy_is_in_join_on_and_base_where():
    plan, context, space = _fixture()
    query = render_tsql_report(plan, policy_columns=policy_columns())
    assert "LEFT JOIN [dbo].[persons_person] AS t2 ON t2.[user_id] = t1.[id] AND t2.[is_deleted] = 0" in query.sql
    assert "WHERE t0.[is_deleted] = 0" in query.sql
    assert validate_tsql_report(query, plan, context, space, policy_columns=policy_columns())
    with pytest.raises(TSQLReportError, match="differ"):
        validate_tsql_report(replace(query, sql=query.sql.replace("SUM(", "AVG(")),
                             plan, context, space, policy_columns=policy_columns())


def test_pilot_removes_unrequested_policy_filters_and_unused_joins():
    catalog = daily_performance_catalog()
    candidates = PlanCandidates(
        {f"t{i}": item for i, item in enumerate(catalog.tables)},
        {f"c{i}": item for i, item in enumerate(catalog.columns)},
        {f"r{i}": item for i, item in enumerate(catalog.relations)}, catalog.definitions,
    )
    ids = {column.key: key for key, column in candidates.columns.items()}
    proposal = PlanProposal(
        "t0", (ProposedJoin("r0", "t1", "inner"), ProposedJoin("r1", "t2", "inner")),
        ids["dbo.functionality_activities.date"], "day",
        (ids["dbo.functionality_activities.date"],),
        (ProposedMeasure("hours", "sum", ids["dbo.functionality_activities.time"]),),
        (ProposedFilter("deleted records", ids["dbo.functionality_activities.is_deleted"], "eq", ("0",)),
         ProposedFilter("deleted records", ids["dbo.persons_person.is_deleted"], "eq", ("0",))),
    )

    class Fake:
        def propose_query_plan(self, *args):
            return proposal

    wrapper = _PilotPlanningProvider(Fake(), policy_columns())
    context = ResolvedContext("all available data", ("date",), ("hours",), (), "")
    result = wrapper.propose_query_plan("daily hours by date", context, candidates)
    assert result.joins == ()
    assert result.filters == ()
    assert result.dimensions == ()
    assert len(wrapper.repairs) == 4


def test_comparison_repeats_filter_bind_values_in_sql_order():
    plan, _, space = _fixture()
    user_id = next(column for column in space.columns
                   if column.key == "dbo.functionality_activities.user_id")
    activity_date = next(column for column in space.columns
                         if column.key == "dbo.functionality_activities.date")
    plan = replace(plan, time_column=activity_date, time_period="January 2026",
                   comparison_period="December 2025", time_grain="day",
                   filters=(PlannedFilter("user 42", user_id, "eq", ("42",)),))
    context = ResolvedContext("January 2026", (), ("activity hours",),
                              ("user 42",), "December 2025")
    query = render_tsql_report(plan, policy_columns=policy_columns(),
                               period_bounds=("2026-01-01", "2026-02-01"),
                               comparison_bounds=("2025-12-01", "2026-01-01"))
    assert query.sql.count("t0.[user_id] = ?") == 2
    assert query.parameters == ("42", "2026-01-01", "2026-02-01",
                                "42", "2025-12-01", "2026-01-01")
    assert validate_tsql_report(query, plan, context, space, policy_columns=policy_columns(),
                                period_bounds=("2026-01-01", "2026-02-01"),
                                comparison_bounds=("2025-12-01", "2026-01-01"))


class _Cursor:
    def __init__(self, writable=False):
        self.writable = writable
        self.statements = []
        self.description = (("dimension_1",), ("metric_1",))

    def execute(self, sql, *params):
        self.statements.append(sql)
        return self

    def fetchone(self):
        return (1, 1, 1, 1) if self.writable else (1, 0, 0, 0)

    def fetchmany(self, size):
        return [("A", 2.0)]


class _Connection:
    def __init__(self, writable=False):
        self._cursor = _Cursor(writable)
        self.closed = False

    def cursor(self):
        return self._cursor

    def rollback(self):
        pass

    def close(self):
        self.closed = True


@pytest.mark.parametrize("writable", [False, True], ids=["read_only_login", "privileged_login"])
def test_login_executes_validated_report_regardless_of_write_permissions(writable):
    plan, context, space = _fixture()
    query = render_tsql_report(plan, policy_columns=policy_columns())
    connection = _Connection(writable=writable)
    result = execute_tsql_report(lambda: connection, query, plan, context, space,
                                 policy_columns=policy_columns())
    assert result.rows == (("A", 2.0),)
    assert connection._cursor.statements == [query.sql]
    assert connection.closed


@pytest.mark.parametrize("unsafe_sql", [
    "INSERT INTO [dbo].[functionality_activities] ([time]) VALUES (1)",
    "UPDATE [dbo].[functionality_activities] SET [time] = 1",
    "DELETE FROM [dbo].[functionality_activities]",
    "MERGE INTO [dbo].[functionality_activities] AS t USING [dbo].[authentication_user] AS s ON t.[user_id] = s.[id] WHEN MATCHED THEN DELETE",
    "CREATE TABLE [dbo].[unsafe] ([id] int)",
    "SELECT 1; SELECT 2",
    "SELECT * FROM [dbo].[unsafe]",
])
def test_unsafe_sql_is_rejected_before_opening_privileged_connection(unsafe_sql):
    plan, context, space = _fixture()
    query = replace(render_tsql_report(plan, policy_columns=policy_columns()), sql=unsafe_sql)
    with pytest.raises(TSQLReportError):
        execute_tsql_report(lambda: pytest.fail("connection must not open"), query,
                            plan, context, space, policy_columns=policy_columns())
