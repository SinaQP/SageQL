"""Independent host schemas through real SDK/agents/adapters, fake model transport."""

from dataclasses import replace
from hashlib import sha256
import importlib.util
import json
from pathlib import Path
import sqlite3
import sys
from types import SimpleNamespace

import pytest

from sageql import LLMConfig, Message
from sageql.sdk import (
    ActorContext, ConceptRef, DimensionDefinition, EntityLabelDimension, Interpretation, OpenAIReportAgent,
    OpenAIReportInterpreter, PeriodSelection, ReportIntent, ReportSpec, SDKError,
    SageQL, SQLiteAdapter, SQLiteSessionStore, UserFilter,
)
from sageql.sdk.adapters import compile_report
from sageql.sdk.business import measure_question, participant_mean_context
from sageql.sdk.intent import canonical_intent
from sageql.sdk.periods import period_evidence_context
from sageql.sdk.provider import _unnecessary_lookup_question
from sageql.sdk.semantics import permitted_catalog, validate_catalog


_SPEC = importlib.util.spec_from_file_location(
    "sageql_multi_domain_demo", Path(__file__).parents[1] / "examples" / "multi_domain.py")
demo = importlib.util.module_from_spec(_SPEC)
sys.modules[_SPEC.name] = demo
_SPEC.loader.exec_module(demo)


class Client:
    def __init__(self, *responses):
        self.responses = iter(responses)
        self.calls = []
        self.chat = SimpleNamespace(completions=self)

    def with_options(self, **options):
        return self

    def create(self, **options):
        self.calls.append(options)
        output = next(self.responses)
        if isinstance(output, Exception):
            raise output
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(
            content=json.dumps(output, ensure_ascii=False)))])


class RecordingAdapter:
    def __init__(self, path):
        self.database = SQLiteAdapter(path)
        self.calls = []
        self.sql = []

    def execute(self, report, limits, *, cancel=None):
        self.calls.append(report)
        self.sql.extend(compile_report(report, limits, dialect=dialect) for dialect in ("sqlite", "tsql"))
        return self.database.execute(report, limits, cancel=cancel)


def intent(spec, **changes):
    return replace(ReportIntent(
        metrics=tuple(ConceptRef(spec.dataset_id, key) for key in spec.metric_ids),
        dimensions=tuple(ConceptRef(spec.dataset_id, key) for key in spec.dimension_ids),
        chart=spec.chart, time_grain=spec.time_grain, period=spec.period, filters=spec.filters,
        aggregate_filters=spec.aggregate_filters, order_by=spec.order_by,
        ordering_specified=True, descending=spec.descending, limit=spec.limit,
    ), **changes).to_dict()


def ready(spec):
    return {"status": "ready", "spec": spec.to_dict(), "question": "", "message": ""}


def agent(client):
    return OpenAIReportAgent(LLMConfig("synthetic-token", "https://example.test/v1", "fake"),
                             client=client, language="en")


@pytest.fixture(params=demo.scenarios(), ids=lambda item: item.name)
def host(request, tmp_path):
    scenario = request.param
    path = tmp_path / (scenario.name + ".sqlite")
    scenario.create_data(path)
    return scenario, path, tmp_path / "sessions.sqlite"


def engine(host, client, **options):
    scenario, path, sessions = host
    return SageQL(catalog=scenario.catalog, database=RecordingAdapter(path), provider=agent(client),
        policy=options.pop("policy", scenario.policy), clock=lambda: demo.TODAY, language="en",
        execution=options.pop("execution", "validated"), sessions=SQLiteSessionStore(sessions), **options)


def submit(sdk, question, *, session=None, revision=0, request="report", actor=demo.ACTOR):
    session = session or sdk.create_session(actor).session_id
    return sdk.submit(session, question, actor, request, revision)


def test_complete_conversation_relationships_execution_and_json_in_each_domain(host):
    scenario, path, _ = host
    before = sha256(path.read_bytes()).hexdigest()
    client = Client(
        intent(scenario.initial, missing=("year",), period=None),
        {"status": "needs_clarification", "spec": None, "question": "Which year should September cover?", "message": ""},
        {"approved": True, "feedback": ""},
        intent(scenario.initial, turn_kind="answer"), ready(scenario.initial), {"approved": True, "feedback": ""},
        intent(scenario.refined, turn_kind="refine"), ready(scenario.refined), {"approved": True, "feedback": ""},
    )
    sdk = engine(host, client)
    first = submit(sdk, scenario.question, request="ask")
    assert first.status == "needs_clarification" and sdk.database.calls == []
    report = submit(sdk, "2026", session=first.session_id, revision=1, request="year")
    assert report.status == "report_ready", report.to_dict()
    assert report.report.rows == scenario.expected
    assert report.report.visualization["kind"] == scenario.initial.chart
    assert report.report.fields[-1].label in report.report.title
    refined = submit(sdk, scenario.refinement, session=first.session_id, revision=2, request="refine")
    assert refined.status == "report_ready", refined.to_dict()
    assert refined.report.rows == scenario.refined_expected
    assert refined.report.visualization["kind"] == scenario.refined.chart
    assert refined.report.provenance["period_start"] == "2026-09-01"
    assert refined.report.provenance["period_end_exclusive"] == "2026-10-01"
    assert json.loads(json.dumps(refined.to_dict())) == refined.to_dict()
    cached = submit(sdk, scenario.refinement, session=first.session_id, revision=2, request="refine")
    assert cached.to_dict() == refined.to_dict() and len(sdk.database.calls) == 2
    resumed = engine(host, Client())
    assert resumed.get_report(first.session_id, refined.report.id, demo.ACTOR) == refined.report
    with pytest.raises(SDKError) as denied:
        resumed.get_report(first.session_id, refined.report.id, ActorContext("another-reader"))
    assert denied.value.code == "access_denied"
    assert sha256(path.read_bytes()).hexdigest() == before
    for call in client.calls:
        payload = call["messages"][1]["content"]
        for private in ("sale_lines", "merchandise", "net_amount", "shop_key", "sku_code", "voided",
                        "circulation_events", '"holdings"', "branch_code", "accession_no", "patron_ref",
                        "retracted", "restricted", "synthetic-token", '"north"', '"4101"',
                        "Private product", "Private title", "Secret shelf", "Field guide", "The night sky"):
            assert private not in payload
        assert "employees" not in call["messages"][0]["content"]
        assert "activity/workload" not in call["messages"][0]["content"]
        assert "rows" not in json.loads(payload)
    for compiled in sdk.database.sql:
        assert "north" not in compiled.sql and "Books" not in compiled.sql
        assert "JOIN" in compiled.sql and compiled.parameters


@pytest.mark.parametrize("execution", ["disabled", "validated"])
def test_execution_opt_in_and_current_source_permissions(host, execution):
    scenario, _, _ = host
    client = Client(intent(scenario.initial), ready(scenario.initial), {"approved": True, "feedback": ""})
    sdk = engine(host, client, execution=execution)
    if execution == "validated":
        original = scenario.policy
        sdk._policy = lambda actor: replace(original(actor), datasets=original(actor).datasets[:1])
    result = submit(sdk, scenario.question + " 2026")
    assert result.report is None and sdk.database.calls == []
    assert result.error["code"] == ("execution_disabled" if execution == "disabled" else "invalid_interpretation")


@pytest.mark.parametrize("output", [{"sql": "SELECT * FROM unregistered_secrets"},
    {"metrics": [{"dataset_id": "unregistered_secrets", "concept_id": "password"}]},
    RuntimeError("private transport credential")])
def test_untrusted_or_failed_model_cannot_reach_a_database(host, output):
    sdk = engine(host, Client(output))
    result = submit(sdk, "Report everything in 2026")
    assert result.report is None and sdk.database.calls == []
    assert result.error["code"] in {"invalid_interpretation", "provider_failed"}
    assert "private transport credential" not in json.dumps(result.to_dict())


def test_duplicate_visible_relationship_keys_fail_closed_in_both_domains(host):
    scenario, path, _ = host
    sql = {
        "retail": "INSERT INTO merchandise SELECT * FROM merchandise WHERE shop_key = 'north' AND sku_code = 'B1'",
        "library": "INSERT INTO holdings SELECT * FROM holdings WHERE branch_code = 'N' AND accession_no = 4102",
    }[scenario.name]
    with sqlite3.connect(path) as connection:
        connection.execute(sql)
    sdk = engine(host, Client(intent(scenario.initial), ready(scenario.initial), {"approved": True, "feedback": ""}))
    result = submit(sdk, scenario.question + " 2026")
    assert result.report is None and result.error["code"] == "relationship_cardinality"


def test_policy_revocation_during_interpretation_blocks_execution_and_saved_reads(host):
    scenario, _, _ = host
    state = {"revoked": False}

    def policy(actor):
        scope = scenario.policy(actor)
        return replace(scope, version="revoked") if state["revoked"] else scope

    client = Client(intent(scenario.initial), ready(scenario.initial), {"approved": True, "feedback": ""})
    sdk = engine(host, client, policy=policy)
    result = submit(sdk, scenario.question + " 2026")
    assert result.status == "report_ready"
    state["revoked"] = True
    with pytest.raises(SDKError) as denied:
        sdk.get_report(result.session_id, result.report.id, demo.ACTOR)
    assert denied.value.code == "access_denied"
    state["revoked"] = False

    class RevokingClient(Client):
        def create(self, **options):
            response = super().create(**options)
            if len(self.calls) == 3:
                state["revoked"] = True
            return response

    sdk.provider = agent(RevokingClient(intent(scenario.initial), ready(scenario.initial),
                                      {"approved": True, "feedback": ""}))
    sdk.database.calls.clear()
    denied = submit(sdk, scenario.question + " 2026", session=result.session_id,
                    revision=result.revision, request="changed")
    assert denied.report is None and denied.error["code"] == "access_denied"
    assert sdk.database.calls == []


def test_live_schema_drift_cannot_be_repaired_by_model_or_guessing(host):
    scenario, path, _ = host
    column = scenario.catalog.datasets[0].time.column
    table = scenario.catalog.datasets[0].table.name
    with sqlite3.connect(path) as connection:
        connection.execute(f'ALTER TABLE "{table}" RENAME COLUMN "{column}" TO "unregistered_date"')
    sdk = engine(host, Client(intent(scenario.initial), ready(scenario.initial), {"approved": True, "feedback": ""}))
    result = submit(sdk, scenario.question + " 2026")
    assert result.report is None and result.error["code"] == "schema_drift"


def named_spec(scenario):
    definition = scenario.catalog.lookups[0]
    name = {"retail": "Field guide", "library": "The night sky"}[scenario.name]
    return replace(scenario.initial, dimension_ids=(), chart="table", order_by=None,
                   filters=(UserFilter(definition.id, "eq", (name,)),))


def test_single_column_entity_name_lookup_uses_bounded_policy_reads_and_no_model_ids(host):
    scenario, _, _ = host
    spec = named_spec(scenario)
    client = Client(intent(spec), ready(spec), {"approved": True, "feedback": ""})
    sdk = engine(host, client)
    result = submit(sdk, "Report for " + spec.filters[0].values[0] + " in September 2026")
    assert result.status == "report_ready", result.to_dict()
    assert result.report.rows == ((scenario.expected[0][1],),)
    assert [item.dataset.id for item in sdk.database.calls] == [scenario.catalog.lookups[0].source_dataset_id, spec.dataset_id]
    assert sdk.database.calls[0].spec.limit == 2
    assert result.report.provenance["filters"][0]["filter_id"] == spec.filters[0].filter_id
    for call in client.calls:
        payload = json.loads(call["messages"][1]["content"])
        assert payload["current_spec"] is None and "results" not in payload
        assert "4102" not in json.dumps(payload) and '"B1"' not in json.dumps(payload)


@pytest.mark.parametrize("inaccessible", ["foreign_scope", "restricted_source", "partial_name"])
def test_single_name_lookup_does_not_bypass_source_policies_or_use_fuzzy_matching(host, inaccessible):
    scenario, _, _ = host
    names = {"retail": {"foreign_scope": "Private product", "restricted_source": "Withdrawn product", "partial_name": "Field"},
             "library": {"foreign_scope": "Private title", "restricted_source": "Restricted title", "partial_name": "night sky"}}
    spec = named_spec(scenario)
    spec = replace(spec, filters=(replace(spec.filters[0], values=(names[scenario.name][inaccessible],)),))
    sdk = engine(host, Client(intent(spec), ready(spec), {"approved": True, "feedback": ""}))
    result = submit(sdk, "A named item report in September 2026")
    assert result.status == "needs_clarification" and result.report is None
    assert len(sdk.database.calls) == 1


@pytest.mark.parametrize("mode", ["missing", "ambiguous"])
def test_entity_name_questions_use_registered_labels_and_do_not_select_a_candidate(host, mode):
    scenario, path, _ = host
    spec = named_spec(scenario)
    if mode == "missing":
        spec = replace(spec, filters=(replace(spec.filters[0], values=("No such item",)),))
    else:
        sql = {
            "retail": "INSERT INTO merchandise VALUES ('north', 'OTHER', 'Field guide', 'Books', 1)",
            "library": "INSERT INTO holdings VALUES ('N', 4999, 'The night sky', 'Science', 0)",
        }[scenario.name]
        with sqlite3.connect(path) as connection:
            connection.execute(sql)
    sdk = engine(host, Client(intent(spec), ready(spec), {"approved": True, "feedback": ""}))
    result = submit(sdk, "A named item report in September 2026")
    assert result.status == "needs_clarification" and result.report is None
    assert scenario.catalog.lookups[0].label in result.text
    assert "employee" not in result.text.casefold() and len(sdk.database.calls) == 1


def test_entity_labels_are_enriched_after_aggregation_with_registered_names(host):
    scenario, _, _ = host
    fact = scenario.catalog.datasets[0]
    label = next(item for item in fact.dimensions if isinstance(item, EntityLabelDimension))
    spec = replace(scenario.initial, dimension_ids=(label.id,), chart="table")
    client = Client(intent(spec), ready(spec), {"approved": True, "feedback": ""})
    sdk = engine(host, client)
    result = submit(sdk, "Rank named items in September 2026")
    assert result.status == "report_ready", result.to_dict()
    expected = {"retail": (("Field guide", scenario.expected[0][1]), ("Seeds", scenario.expected[1][1])),
                "library": (("The night sky", 3), ("A brief history", 1))}[scenario.name]
    assert result.report.rows == expected and len(sdk.database.calls) == 2
    for call in client.calls:
        payload = call["messages"][1]["content"]
        assert "Field guide" not in payload and "The night sky" not in payload


def test_legacy_lookup_repair_uses_registered_identity_vocabulary(host):
    scenario, _, _ = host
    spec = named_spec(scenario)
    identity_label = scenario.catalog.datasets[0].filters[0].label
    question = "Please provide the " + identity_label + "."
    assert _unnecessary_lookup_question(Interpretation("needs_clarification", question=question), scenario.catalog)
    assert _unnecessary_lookup_question(Interpretation("needs_clarification", question="What is the " + identity_label + "?"), scenario.catalog)
    client = Client({"status": "needs_clarification", "spec": None, "question": question, "message": ""}, ready(spec))
    provider = OpenAIReportInterpreter(LLMConfig("fake"), client=client, language="en")
    allowed = permitted_catalog(scenario.catalog, scenario.policy(demo.ACTOR))
    result = provider.interpret((Message("user", "A named report in September 2026"),), None, allowed, demo.TODAY)
    assert result.spec == spec and len(client.calls) == 2
    genuine = "Which year should September cover for " + identity_label + " 42?"
    assert not _unnecessary_lookup_question(Interpretation("needs_clarification", question=genuine), allowed)


def test_identity_display_respects_host_terms_and_explicit_output_limits(host):
    scenario, _, _ = host
    fact = scenario.catalog.datasets[0]
    label = next(item for item in fact.dimensions if isinstance(item, EntityLabelDimension))
    identity = next(item for item in fact.dimensions if type(item) is DimensionDefinition and item.column == label.column)
    value = ReportIntent(metrics=(ConceptRef(fact.id, fact.metrics[0].id),), chart="table",
                         dimensions=(ConceptRef(fact.id, identity.id), ConceptRef(fact.id, label.id)))
    assert canonical_intent(value, scenario.catalog, messages=(Message("user", "Show " + identity.label),)).dimensions == value.dimensions
    removed = canonical_intent(value, scenario.catalog, messages=(Message("user", "Remove " + identity.label),))
    assert removed.dimensions == (ConceptRef(fact.id, label.id),)
    counted = replace(value, time_grain="month", limit=2)
    message = Message("user", "روند سه ماه گذشته برای دو کتابخانه")
    assert period_evidence_context(counted, (message,), scenario.catalog).limit == 2
    assert period_evidence_context(counted, (Message("user", "روند سه ماه گذشته"),), scenario.catalog).limit == 100
    question = measure_question(scenario.catalog, "en").question
    assert fact.metrics[0].label in question and "hours" not in question.casefold()


def test_participant_mean_and_row_average_are_distinguished_by_host_vocabulary():
    catalog = demo.library_catalog()
    value = ReportIntent(metrics=(ConceptRef("loans", "mean_duration"),), time_grain="none")
    message = Message("user", "Average loan days per reader and mean loan duration")
    result = participant_mean_context(value, (message,), catalog, None)
    assert {ref.concept_id for ref in result.metrics} == {"mean_duration", "days_per_reader"}
    only_mean = participant_mean_context(value, (Message("user", "Average loan days per reader"),), catalog, None)
    # Explicit registered row-average vocabulary preserves both requested concepts.
    assert {ref.concept_id for ref in only_mean.metrics} == {"mean_duration", "days_per_reader"}
    only_mean = participant_mean_context(value, (Message("user", "Mean days per reader"),), catalog, None)
    assert {ref.concept_id for ref in only_mean.metrics} == {"days_per_reader"}


@pytest.mark.parametrize("names", [(), ("sku_name", "sku_name"), ("sku_name",) * 5, ("sellable",), ("unregistered",)])
def test_single_name_extension_retains_column_and_expression_validation(names):
    catalog = demo.retail_catalog()
    source = catalog.datasets[1]
    updated = replace(source, filters=tuple(replace(item, name_columns=names) if item.id == "title_filter" else item
                                            for item in source.filters))
    with pytest.raises(SDKError) as invalid:
        validate_catalog(replace(catalog, datasets=(catalog.datasets[0], updated)))
    assert invalid.value.code == "invalid_catalog"
