"""Run one locally configured SageQL question against approved Rahtal tables."""

from __future__ import annotations

import argparse
import json
import os
import re
import runpy
import sys
import time
from dataclasses import asdict, dataclass, replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable
from uuid import uuid4

from dotenv import dotenv_values

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))

from sageql.chat_provider import OpenAIChatProvider  # noqa: E402
from sageql.context import ContextResolutionSession  # noqa: E402
from sageql.conversation import ChatConfig, DatabaseConfig, LLMConfig  # noqa: E402
from sageql.discovery import QuerySpace, discover_query_space  # noqa: E402
from sageql.discovery import DiscoveryError  # noqa: E402
from sageql.planning import PlanningError, create_query_plan, review_query_plan  # noqa: E402
from sageql.schema import Column, SchemaCatalog  # noqa: E402
from sageql.tsql import TSQLReportError, execute_tsql_report, render_tsql_report, validate_tsql_report  # noqa: E402
from sageql.understanding import RequestUnderstandingSession  # noqa: E402

from sageql_rahtal.catalog import daily_performance_catalog, policy_columns  # noqa: E402


class NeedsClarification(Exception):
    """The question needs another user-written detail before querying data."""


@dataclass(frozen=True)
class LocalConfig:
    question: str
    question_file: str | None
    run_mode: str
    env_file: str | None
    reports_dir: str | None
    period_start: str | None
    period_end: str | None
    comparison_start: str | None
    comparison_end: str | None
    max_rows: int
    timeout_seconds: int
    llm_timeout_seconds: int


def _load_local_config(path: Path) -> LocalConfig:
    if not path.is_file():
        raise ValueError("local config is missing; copy local_config.example.py to local_config.py")
    try:
        values = runpy.run_path(str(path))
    except Exception:
        raise ValueError("local config could not be loaded; check its Python syntax") from None

    def optional_text(name: str) -> str | None:
        value = values.get(name)
        if value is not None and (not isinstance(value, str) or not value.strip()):
            raise ValueError(f"{name} must be text or None")
        return value

    question = values.get("QUESTION", "")
    if not isinstance(question, str):
        raise ValueError("QUESTION must be text")
    mode = values.get("RUN_MODE", "validate")
    if mode not in {"validate", "execute"}:
        raise ValueError("RUN_MODE must be 'validate' or 'execute'")
    max_rows = values.get("MAX_ROWS", 100)
    timeout = values.get("TIMEOUT_SECONDS", 10)
    llm_timeout = values.get("LLM_TIMEOUT_SECONDS", 60)
    if type(max_rows) is not int or not 1 <= max_rows <= 1000:
        raise ValueError("MAX_ROWS must be an integer from 1 to 1000")
    if type(timeout) is not int or not 1 <= timeout <= 60:
        raise ValueError("TIMEOUT_SECONDS must be an integer from 1 to 60")
    if type(llm_timeout) is not int or not 5 <= llm_timeout <= 180:
        raise ValueError("LLM_TIMEOUT_SECONDS must be an integer from 5 to 180")
    return LocalConfig(
        question, optional_text("QUESTION_FILE"), mode,
        optional_text("ENV_FILE"), optional_text("REPORTS_DIR"),
        optional_text("PERIOD_START"), optional_text("PERIOD_END"),
        optional_text("COMPARISON_START"), optional_text("COMPARISON_END"),
        max_rows, timeout, llm_timeout,
    )


def _resolve_options(args: argparse.Namespace, config: LocalConfig, config_path: Path) -> argparse.Namespace:
    """Combine local defaults and one-off CLI overrides before any model call."""
    base = config_path.resolve().parent

    def local_path(value: str | None, fallback: Path) -> Path:
        if value is None:
            return fallback
        path = Path(value)
        return path if path.is_absolute() else base / path

    fallback_env = HERE / ".env" if (HERE / ".env").exists() else Path("D:/Coding/QuerySmith/rahtal/.env")
    question_path = Path(args.question) if args.question else (
        local_path(config.question_file, HERE / "question.txt") if not config.question.strip() else None
    )
    question_text = None if args.question else config.question.strip() or None
    period_start = args.period_start if args.period_start is not None else config.period_start
    period_end = args.period_end if args.period_end is not None else config.period_end
    comparison_start = (args.comparison_start if args.comparison_start is not None
                        else config.comparison_start)
    comparison_end = args.comparison_end if args.comparison_end is not None else config.comparison_end
    if bool(period_start) != bool(period_end):
        raise ValueError("PERIOD_START and PERIOD_END must both be set or both be empty")
    if bool(comparison_start) != bool(comparison_end):
        raise ValueError("COMPARISON_START and COMPARISON_END must both be set or both be empty")
    max_rows = args.max_rows if args.max_rows is not None else config.max_rows
    timeout = args.timeout if args.timeout is not None else config.timeout_seconds
    if type(max_rows) is not int or not 1 <= max_rows <= 1000:
        raise ValueError("max rows must be an integer from 1 to 1000")
    if type(timeout) is not int or not 1 <= timeout <= 60:
        raise ValueError("timeout must be an integer from 1 to 60 seconds")
    return argparse.Namespace(
        config=str(config_path.resolve()), question_path=question_path, question_text=question_text,
        env=Path(args.env) if args.env else local_path(config.env_file, fallback_env),
        reports=Path(args.reports) if args.reports else local_path(config.reports_dir, HERE / "reports"),
        period_start=period_start, period_end=period_end,
        comparison_start=comparison_start, comparison_end=comparison_end,
        max_rows=max_rows, timeout=timeout,
        llm_timeout=config.llm_timeout_seconds,
        no_execute=args.no_execute if args.no_execute is not None else config.run_mode == "validate",
    )


def _load_settings(path: Path) -> dict[str, str]:
    values = {key: value for key, value in dotenv_values(path).items() if value}
    values.update({key: value for key, value in os.environ.items()
                   if key.startswith("RAHTAL_") and value})
    required = ("RAHTAL_DB_SERVER", "RAHTAL_DB_DATABASE", "RAHTAL_DB_USERNAME",
                "RAHTAL_DB_PASSWORD", "RAHTAL_LLM_API_KEY", "RAHTAL_LLM_BASE_URL",
                "RAHTAL_LLM_MODEL")
    missing = [key for key in required if not values.get(key)]
    if missing:
        raise ValueError("missing settings: " + ", ".join(missing))
    values.setdefault("RAHTAL_DB_DRIVER", "ODBC Driver 18 for SQL Server")
    values.setdefault("RAHTAL_DB_SCHEMA", "dbo")
    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", values["RAHTAL_DB_SCHEMA"]):
        raise ValueError("RAHTAL_DB_SCHEMA must be a simple schema name")
    return values


def _connect(settings: dict[str, str]):
    import pyodbc

    def wrap(value: str) -> str:
        return "{" + value.replace("}", "}}") + "}"

    connection_string = ";".join((
        "DRIVER=" + wrap(settings["RAHTAL_DB_DRIVER"]),
        "SERVER=" + wrap(settings["RAHTAL_DB_SERVER"]),
        "DATABASE=" + wrap(settings["RAHTAL_DB_DATABASE"]),
        "UID=" + wrap(settings["RAHTAL_DB_USERNAME"]),
        "PWD=" + wrap(settings["RAHTAL_DB_PASSWORD"]),
        "ApplicationIntent=ReadOnly", "TrustServerCertificate=yes",
    ))
    return pyodbc.connect(connection_string, autocommit=False, timeout=5)


def _check_live_catalog(settings: dict[str, str], static: SchemaCatalog) -> SchemaCatalog:
    """Verify every approved column exists; copy its actual SQL Server type."""
    connection = _connect(settings)
    try:
        connection.timeout = 10
        cursor = connection.cursor()
        schema = settings["RAHTAL_DB_SCHEMA"]
        names = tuple(table.name for table in static.tables)
        rows = cursor.execute(
            "SELECT TABLE_NAME, COLUMN_NAME, DATA_TYPE, IS_NULLABLE "
            "FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_SCHEMA = ? "
            "AND TABLE_NAME IN (?, ?, ?)", schema, *names,
        ).fetchall()
        found = {(row[0], row[1]): (row[2], row[3] == "YES") for row in rows}
        missing = [column.key for column in static.columns
                   if (column.table.split(".")[-1], column.name) not in found]
        if missing:
            raise ValueError("approved columns are absent from the live database: " + ", ".join(missing))
        columns = tuple(Column(column.table, column.name,
                               *found[(column.table.split(".")[-1], column.name)])
                        for column in static.columns)
        return SchemaCatalog(static.tables, columns, static.relations, static.definitions)
    finally:
        connection.rollback()
        connection.close()


def _include_policy_columns(space: QuerySpace, catalog: SchemaCatalog,
                            policies: dict[str, str]) -> QuerySpace:
    selected = {column.key for column in space.columns}
    added = tuple(column for column in catalog.columns
                  if column.table in {table.key for table in space.tables}
                  and column.name == policies.get(column.table)
                  and column.key not in selected)
    return QuerySpace(space.tables, (*space.columns, *added), space.relations, space.definitions)


class _PilotPlanningProvider:
    """Keep policy and unused schema paths out of the model's logical plan."""

    def __init__(self, provider: OpenAIChatProvider, policies: dict[str, str]) -> None:
        self.provider = provider
        self.policies = policies
        self.proposal = None
        self.repairs: list[str] = []

    def propose_query_plan(self, understanding, context, candidates):
        proposal = self.provider.propose_query_plan(understanding, context, candidates)
        self.proposal = proposal
        if proposal.base_table_id not in candidates.tables:
            return proposal
        allowed_policy_keys = {f"{table}.{column}" for table, column in self.policies.items()}
        filters = []
        for item in proposal.filters:
            column = candidates.columns.get(item.column_id)
            policy_equivalent = (
                (item.operator == "eq" and tuple(value.casefold() for value in item.values)
                 in {("0",), ("false",)})
                or (item.operator == "neq" and tuple(value.casefold() for value in item.values)
                    in {("1",), ("true",)})
            )
            if (column and column.key in allowed_policy_keys
                    and item.source_filter not in context.filters and policy_equivalent):
                self.repairs.append(f"Moved {column.key} soft-delete policy into deterministic SQL.")
            elif column and column.key in allowed_policy_keys and not policy_equivalent:
                raise PlanningError("this pilot cannot report deleted activity or profile rows")
            else:
                filters.append(item)
        dimensions = tuple(value for value in proposal.dimensions
                           if not (value == proposal.time_column_id and proposal.time_grain != "none"))
        if len(dimensions) != len(proposal.dimensions):
            self.repairs.append("Removed duplicate time grouping dimension.")
        referenced_ids = [proposal.time_column_id, *dimensions,
                          *(item.column_id for item in proposal.measures),
                          *(item.column_id for item in filters)]
        needed = {candidates.columns[item].table for item in referenced_ids
                  if item in candidates.columns}
        needed.add(candidates.tables[proposal.base_table_id].key)
        kept = []
        for item in reversed(proposal.joins):
            to_table = candidates.tables.get(item.to_table_id)
            relation = candidates.relations.get(item.relation_id)
            if to_table and relation and to_table.key in needed:
                kept.append(item)
                needed.update((relation.child_table, relation.parent_table))
        kept.reverse()
        if len(kept) != len(proposal.joins):
            self.repairs.append("Removed joins unused by the report fields and filters.")
        if any(item.join_type == "inner" for item in kept):
            kept = [replace(item, join_type="left") for item in kept]
            self.repairs.append("Changed joins to LEFT to preserve activity rows without linked details.")
        return replace(proposal, joins=tuple(kept), dimensions=dimensions, filters=tuple(filters))


def _safe_error(exc: Exception) -> str:
    if isinstance(exc, (NeedsClarification, ValueError, PlanningError, DiscoveryError, TSQLReportError)):
        return str(exc)
    # Library, provider and driver errors can include connection strings or row data.
    return f"{type(exc).__name__}: this stage failed; inspect the local configuration and question"


def _save(report: dict[str, Any], folder: Path) -> tuple[Path, Path]:
    folder.mkdir(parents=True, exist_ok=True)
    request_id = report["request_id"]
    json_path = folder / f"{request_id}.json"
    md_path = folder / f"{request_id}.md"
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    lines = ["# SageQL Rahtal test report", "", f"- Run: `{request_id}`",
             f"- Status: **{report['status']}**", f"- Started: {report['started_at']}",
             f"- Total time: {report['total_ms']} ms", "", "## Question", "",
             report["question"], ""]
    for stage in report["stages"]:
        lines.extend((f"## {stage['stage']}", "", f"Status: **{stage['status']}** · {stage['elapsed_ms']} ms",
                      "", "```json", json.dumps(stage.get("details", {}), ensure_ascii=False,
                                                indent=2, default=str), "```", ""))
    if report.get("error"):
        lines.extend(("## Failure", "", report["error"], ""))
    md_path.write_text("\n".join(lines), encoding="utf-8")
    return json_path, md_path


def run(args: argparse.Namespace) -> int:
    request_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + uuid4().hex[:8]
    started = time.perf_counter()
    report: dict[str, Any] = {"request_id": request_id,
                              "started_at": datetime.now(timezone.utc).isoformat(),
                              "question": "", "status": "running", "stages": []}
    folder = (Path(args.reports) if args.reports else HERE / "reports").resolve()

    def stage(name: str, work: Callable[[], Any], summary: Callable[[Any], Any],
              failure_summary: Callable[[], dict[str, Any]] | None = None) -> Any:
        tick = time.perf_counter()
        try:
            value = work()
        except Exception as exc:
            details = {"error": _safe_error(exc)}
            if failure_summary is not None:
                details.update(failure_summary())
            report["stages"].append({"stage": name, "status": "failed",
                                     "elapsed_ms": round((time.perf_counter() - tick) * 1000, 2),
                                     "details": details})
            raise
        report["stages"].append({"stage": name, "status": "passed",
                                 "elapsed_ms": round((time.perf_counter() - tick) * 1000, 2),
                                 "details": summary(value)})
        return value

    try:
        config_path = Path(args.config)
        local = stage("Local config", lambda: _load_local_config(config_path),
                      lambda value: {"source": str(config_path.resolve()),
                                     "run_mode": value.run_mode,
                                     "question_location": "QUESTION" if value.question.strip()
                                     else "QUESTION_FILE"})
        args = stage("Run options", lambda: _resolve_options(args, local, config_path),
                     lambda value: {"question_source": "local config" if value.question_text is not None
                                    else str(value.question_path.resolve()),
                                    "env_source": str(value.env.resolve()),
                                    "report_folder": str(value.reports.resolve()),
                                    "run_mode": "validate" if value.no_execute else "execute",
                                    "period_bounds": [value.period_start, value.period_end],
                                    "comparison_bounds": [value.comparison_start, value.comparison_end],
                                    "max_rows": value.max_rows, "timeout_seconds": value.timeout,
                                    "llm_timeout_seconds": value.llm_timeout})
        folder = Path(args.reports).resolve()

        def read_question() -> str:
            if args.question_text is not None:
                return args.question_text
            return args.question_path.read_text(encoding="utf-8").strip()

        question = stage("1. Input question", read_question,
                         lambda value: {"question": value,
                                        "source": "local config" if args.question_text is not None
                                        else str(args.question_path.resolve())})
        if not question:
            raise ValueError("question file is empty")
        report["question"] = question
        settings = stage("Configuration", lambda: _load_settings(Path(args.env)),
                         lambda value: {"database_configured": True, "schema": value["RAHTAL_DB_SCHEMA"],
                                        "llm_model": value["RAHTAL_LLM_MODEL"]})
        config = ChatConfig(
            DatabaseConfig(settings["RAHTAL_DB_SERVER"], settings["RAHTAL_DB_DATABASE"],
                           "SQL login", settings["RAHTAL_DB_DRIVER"]),
            LLMConfig(settings["RAHTAL_LLM_API_KEY"], settings["RAHTAL_LLM_BASE_URL"],
                      settings["RAHTAL_LLM_MODEL"]),
        )
        from openai import OpenAI

        provider = OpenAIChatProvider(
            config.llm,
            client=OpenAI(api_key=config.llm.api_key, base_url=config.llm.base_url,
                          timeout=args.llm_timeout, max_retries=0),
        )
        understanding_session = RequestUnderstandingSession(config, provider)
        assessment = stage("2. Request understanding", lambda: understanding_session.submit(question), asdict)
        if not assessment.enough_information:
            raise NeedsClarification(assessment.clarification_question)
        context_session = ContextResolutionSession(
            config, provider, understanding_session.history, assessment.request_understanding)
        resolution = stage("3. Context resolution", context_session.start, asdict)
        if not resolution.ready:
            raise NeedsClarification(resolution.clarification_question)
        context = resolution.context
        schema = settings["RAHTAL_DB_SCHEMA"]
        catalog = stage("4a. Live catalog verification",
                        lambda: _check_live_catalog(settings, daily_performance_catalog(schema)),
                        lambda value: {"tables": [table.key for table in value.tables],
                                       "columns": [asdict(column) for column in value.columns],
                                       "relations": [relation.name for relation in value.relations]})
        space = stage("4b. Query space discovery",
                      lambda: _include_policy_columns(discover_query_space(
                          catalog, provider, assessment.request_understanding, context),
                          catalog, policy_columns(schema)),
                      lambda value: {"tables": [table.key for table in value.tables],
                                     "columns": [column.key for column in value.columns],
                                     "relations": [relation.name for relation in value.relations],
                                     "definitions": [definition.term for definition in value.definitions]})
        planning_provider = _PilotPlanningProvider(provider, policy_columns(schema))

        def make_plan():
            value = create_query_plan(assessment.request_understanding, context, space, planning_provider)
            if value.base_table.key != f"{schema}.functionality_activities":
                raise PlanningError("daily-performance pilot requires activities as the base table")
            return replace(value, repairs=(*value.repairs, *planning_provider.repairs))

        plan = stage("6. Query planning", make_plan,
                     lambda value: {"model_proposal": asdict(planning_provider.proposal),
                                    "operations": value.operations(), "repairs": value.repairs,
                                    "quality": asdict(review_query_plan(value, context, space))},
                     lambda: {"model_proposal": asdict(planning_provider.proposal)
                              if planning_provider.proposal else None,
                              "attempted_repairs": planning_provider.repairs})
        bounds = ((args.period_start, args.period_end) if args.period_start and args.period_end else None)
        comparison = ((args.comparison_start, args.comparison_end)
                      if args.comparison_start and args.comparison_end else None)
        policies = policy_columns(schema)
        query = stage("7. SQL generation",
                      lambda: render_tsql_report(plan, policy_columns=policies,
                                                 period_bounds=bounds, comparison_bounds=comparison),
                      lambda value: {"sql": value.sql, "parameter_names": value.parameter_names,
                                     "parameters": value.parameters})
        checks = stage("8. Validation and safety",
                       lambda: validate_tsql_report(query, plan, context, space,
                                                    policy_columns=policies,
                                                    period_bounds=bounds, comparison_bounds=comparison),
                       lambda value: {"checks_passed": value, "allowed_tables": [t.key for t in space.tables],
                                      "soft_delete_policies": policies,
                                      "row_limit": args.max_rows, "timeout_seconds": args.timeout})
        if not args.no_execute:
            result = stage("9. Query execution",
                           lambda: execute_tsql_report(lambda: _connect(settings), query, plan, context, space,
                                                       policy_columns=policies, period_bounds=bounds,
                                                       comparison_bounds=comparison,
                                                       max_rows=args.max_rows, timeout_seconds=args.timeout),
                           lambda value: {"columns": value.columns, "row_count": len(value.rows),
                                          "truncated": value.truncated, "rows": value.rows})
            report["row_count"] = len(result.rows)
        report["status"] = "completed" if not args.no_execute else "validated_not_executed"
        return_code = 0
    except NeedsClarification as exc:
        report["status"] = "needs_clarification"
        report["error"] = str(exc)
        return_code = 2
    except Exception as exc:
        report["status"] = "failed"
        report["error"] = _safe_error(exc)
        return_code = 1
    finally:
        report["total_ms"] = round((time.perf_counter() - started) * 1000, 2)
        json_path, md_path = _save(report, folder)
        print(f"Status: {report['status']}; rows: {report.get('row_count', 0)}")
        print(f"Report: {md_path}")
        print(f"JSON: {json_path}")
        if report.get("error"):
            print(f"Reason: {report['error']}")
    return return_code


def main() -> int:
    parser = argparse.ArgumentParser(description="Run one SageQL Rahtal question from local config")
    parser.add_argument("--config", default=str(HERE / "local_config.py"))
    parser.add_argument("--question", help="Override QUESTION with a UTF-8 text file")
    parser.add_argument("--env", help="Override ENV_FILE")
    parser.add_argument("--reports", help="Override REPORTS_DIR")
    parser.add_argument("--period-start")
    parser.add_argument("--period-end")
    parser.add_argument("--comparison-start")
    parser.add_argument("--comparison-end")
    parser.add_argument("--max-rows", type=int)
    parser.add_argument("--timeout", type=int)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--execute", dest="no_execute", action="store_const", const=False,
                      help="Override RUN_MODE and execute with a SELECT-only login")
    mode.add_argument("--no-execute", dest="no_execute", action="store_const", const=True,
                      help="Override RUN_MODE and stop after SQL validation")
    parser.set_defaults(no_execute=None)
    return run(parser.parse_args())


if __name__ == "__main__":
    raise SystemExit(main())
