"""A ranking direction without a chosen measure must ask, not sort by a default."""
from dataclasses import replace
from datetime import date
import json
from types import SimpleNamespace

from evaluations.phase05_hosts import host
from evaluations.phase14 import load_cases
from sageql import LLMConfig, Message
from sageql.sdk import ConceptRef, PeriodSelection, ReportIntent
from sageql.sdk.evidence import anchor_intent, request_evidence

CASE = load_cases('independent', ['N06'])[0]
CATALOG = host(CASE['domain'], CASE['host_version'])[0]
MESSAGES = (Message('user', CASE['turns'][0]['request']),)
# Exact intent mini returned live for this turn (round 3): measure missing.
INTENT = ReportIntent(dimensions=(ConceptRef('sales', 'department'),), missing=('measure',),
                      period=PeriodSelection('month', year=2026, month=9), filters=(), aggregate_filters=(),
                      ordering_specified=True, descending=True)


class Client:
    def __init__(self, *responses):
        self.responses, self.calls = list(responses), []
        self.chat = SimpleNamespace(completions=self)

    def with_options(self, **options):
        return self

    def create(self, **options):
        self.calls.append(options)
        value = self.responses.pop(0)
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(
            content=json.dumps(value.to_dict() if isinstance(value, ReportIntent) else value)))])


def test_direction_is_kept_but_default_metric_is_not_imposed_while_measure_is_missing():
    evidence = request_evidence(MESSAGES, CATALOG, None)
    assert evidence.ordering is not None and evidence.ordering.descending is True
    anchored = anchor_intent(INTENT, evidence)
    assert anchored.order_by is None and anchored.descending is True
    assert anchored.missing == ('measure',)


def test_selected_measure_still_receives_the_grounded_target():
    evidence = request_evidence(MESSAGES, CATALOG, None)
    target = evidence.ordering.target
    chosen = replace(INTENT, metrics=(ConceptRef('sales', target),), missing=())
    assert anchor_intent(chosen, evidence).order_by == target


def test_live_path_asks_for_the_measure_instead_of_rejecting_the_intent():
    from sageql.sdk import OpenAIReportAgent
    question = {'status': 'needs_clarification', 'spec': None,
                'question': 'Which measure should rank the departments?', 'message': ''}
    client = Client(INTENT, question, {'approved': True, 'feedback': ''})
    agent = OpenAIReportAgent(LLMConfig('k', 'https://example.test', 'm'), client=client, language='en')
    decision = agent.interpret(MESSAGES, None, CATALOG, date(2026, 10, 29))
    assert decision.status == 'needs_clarification'
    assert len(client.calls) == 3
