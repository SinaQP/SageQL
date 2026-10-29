"""Mock protocol probes and allowlisted observation of the actual SDK transport."""
from collections import Counter
from dataclasses import replace
import json
import re
from time import perf_counter
from types import SimpleNamespace

from sageql.sdk import UserFilter
from sageql.sdk.vocabulary import project_payload
from sageql.sdk.provider import _unique_object, _reject_constant
from evaluations.runner import ScriptedClient, extracted, ready
from evaluations.trajectories import CorrelatedFaultClient, StageClient, responses
from evaluations.phase06_runtime import usage_metadata


REFERENCE = re.compile(r'__sageql_value_\d+_\d+_\d+__')


def protocol_observation(options, decoded):
    """Counts only; no wire scalar, raw output or user text enters artifacts."""
    payload = json.loads(options['messages'][-1]['content'])
    def predicates(value, owner=None):
        if isinstance(value, dict):
            owner = value.get('dataset_id', owner)
            owners = {ref['dataset_id'] for key in ('metrics', 'dimensions') for ref in value.get(key, []) or []
                      if isinstance(ref, dict) and isinstance(ref.get('dataset_id'), str)}
            if len(owners) == 1:
                owner = next(iter(owners))
            if 'filter_id' in value and isinstance(value.get('values'), list):
                for scalar in value['values']:
                    yield owner, value['filter_id'], scalar
            for item in value.values():
                yield from predicates(item, owner)
        elif isinstance(value, list):
            for item in value:
                yield from predicates(item, owner)
    issued = {(owner, identifier, scalar) for owner, identifier, scalar in predicates(payload)
              if isinstance(scalar, str) and REFERENCE.fullmatch(scalar)}
    tokens = {item[2] for item in issued}
    result = Counter(issued=len(tokens), valid=0, fabricated=0, modified=0, wrong_owner=0,
                     scalar_instead_of_reference=0, display_reference=0, malformed_json=int(decoded is None))
    if decoded is None:
        return dict(result)
    for owner, identifier, scalar in predicates(decoded):
        if not isinstance(scalar, str):
            continue
        if REFERENCE.fullmatch(scalar):
            result['valid' if (owner, identifier, scalar) in issued else
                   'wrong_owner' if scalar in tokens else 'fabricated'] += 1
        elif 'sageql' in scalar.casefold() and 'value' in scalar.casefold():
            result['modified'] += 1
        elif any(item[:2] == (owner, identifier) for item in issued):
            result['scalar_instead_of_reference'] += 1
    if isinstance(decoded, dict):
        result['model_sql_attempt'] = int(any(key in decoded for key in ('sql', 'code', 'query')))
        for key in ('question', 'message', 'feedback', 'unsupported_reason'):
            if isinstance(decoded.get(key), str) and 'sageql_value' in decoded[key].casefold():
                result['display_reference'] += 1
    return dict(result)


class ObservedClient(StageClient):
    """Same injected-client protocol as the SDK; no transport retries/fallback."""
    def with_options(self, **options):
        return ObservedClient(self.delegate.with_options(**options), budget=self.budget, state=self.state)

    def create(self, **options):
        ticket = self.budget.reserve(options) if self.budget else None
        self.calls.append(options)
        stage = {'sageql_report_intent': 'intent', 'sageql_report_interpretation': 'planning',
                 'sageql_report_review': 'review'}[options['response_format']['json_schema']['name']]
        stages = [call['response_format']['json_schema']['name'] for call in self.calls]
        recovering = stages.count('sageql_report_interpretation') > 1 or stages.count('sageql_report_intent') > 1
        record = {'stage': stage, 'elapsed_ms': None, 'usage': None, 'failed': False, 'recovery': recovering}
        if stage == 'review':
            record['candidate'] = json.loads(options['messages'][-1]['content'])['candidate']
        started = perf_counter()
        invalid_usage = False
        uncertain = False
        try:
            response = self.delegate.chat.completions.create(**options)
            try:
                record['usage'] = usage_metadata(response)
            except ValueError:
                invalid_usage = True
            if self.budget:
                self.budget.capture_response(ticket, response, record['usage'])
            try:
                # The SDK decoder still independently rejects duplicates/nonfinite/extra fields.
                raw = response.choices[0].message.content
                if not isinstance(raw, str) or len(raw) > 128000:
                    raise ValueError
                record['decoded'] = json.loads(raw, object_pairs_hook=_unique_object, parse_constant=_reject_constant)
            except (ValueError, TypeError, AttributeError, IndexError, RecursionError):
                record['decoded'] = None
            return response
        except Exception:
            record['failed'] = True
            raise
        except BaseException:
            record['failed'] = True
            uncertain = True
            raise
        finally:
            record['elapsed_ms'] = round((perf_counter() - started) * 1000, 3)
            record['protocol'] = ({'transport_error': 1} if record['failed'] else
                                  protocol_observation(options, record.get('decoded')))
            self.records.append(record)
            if self.budget and not uncertain:
                self.budget.settle(ticket, record['usage'], failed=record['failed'], invalid=invalid_usage)


class ProtocolClient:
    """Controlled response scripts, explicitly not model reasoning measurements."""
    def __init__(self, turn, target, catalog):
        # Script v2: legacy author metadata is not a wire-schema enum. Real
        # provider output still passes the unchanged strict SDK decoder.
        self.turn, self.target, self.catalog = dict(turn), target, catalog
        if self.turn.get('turn_kind') == 'refinement':
            self.turn['turn_kind'] = 'refine'
        self.chat = SimpleNamespace(completions=self)
        self.plans = 0

    def with_options(self, **options):
        return self

    def create(self, **options):
        stage = options['response_format']['json_schema']['name']
        fault = self.turn.get('protocol_fault')
        if stage == 'sageql_report_intent':
            value = extracted(self.target, turn_kind=self.turn.get('turn_kind', 'new'))
            if self.turn['expect']['kind'] == 'clarification':
                value = responses(self.turn, self.target)[0]
            if self.turn.get('semantic_fault') in ('omitted_intent', 'persistent_omission'):
                value['filters'] = []
        elif stage == 'sageql_report_review':
            reject = self.turn.get('semantic_fault') == 'review_rejects_correct' and self.plans == 1
            value = {'approved': not reject, 'feedback': 'Please check the requested grouping.' if reject else ''}
        else:
            self.plans += 1
            value = ready(self.target)
            if self.turn['expect']['kind'] == 'clarification':
                value = responses(self.turn, self.target)[1]
            if self.turn.get('semantic_fault') in ('omitted_intent', 'persistent_omission') and (
                    self.plans == 1 or self.turn['semantic_fault'] == 'persistent_omission'):
                value = ready(replace(self.target, filters=()))
            if self.turn.get('semantic_fault') == 'wrong_plan_filter' and self.plans == 1:
                value = ready(replace(self.target, filters=(UserFilter('service_filter', 'eq', ('Web',)),)))
        value = project_payload(value, self.catalog)
        value.pop('host_value_reference_rule', None)  # Request instructions are not response-schema fields.
        if fault and self.turn.get('fault_stage', 'sageql_report_interpretation') in ('all', stage):
            if fault == 'provider_error':
                raise RuntimeError('PRIVATE_PROVIDER_EXCEPTION')
            if fault == 'malformed':
                return ScriptedClient(['{"status":']).create(**options)
            if fault == 'duplicate_key':
                raw = json.dumps(value)
                return ScriptedClient([raw[:-1] + ',"status":"ready"}']).create(**options)
            if fault == 'extra_sql':
                value['sql'] = 'DROP TABLE private_table'
            if fault == 'display':
                value = {'status': 'needs_clarification', 'spec': None,
                         'question': '__sageql_value_0_0_0__', 'message': ''}
            if fault == 'fabricated' and value.get('filters'):
                value['filters'][0]['values'] = ['__sageql_value_99_99_99__']
            if value.get('spec') and value['spec']['filters']:
                condition = value['spec']['filters'][0]
                token = condition['values'][0]
                if fault == 'fabricated': condition['values'] = ['__sageql_value_99_99_99__']
                if fault == 'modified': condition['values'] = [token[:-1]]
                if fault == 'wrong_owner': condition['filter_id'] = 'service_filter'
                if fault == 'canonical': condition['values'] = ['Web']
                if fault == 'missing': value['spec']['filters'] = []
                if fault == 'wrong_concept': value['spec']['metric_ids'] = [token]
                if fault == 'context_reuse': condition['values'] = ['__sageql_value_0_0_0__']
        response = ScriptedClient([value]).create(**options)
        # Mocks deliberately omit usage, unless a unit test explicitly supplies it.
        return response


def mock_client(turn, target, catalog):
    if turn.get('fault'):
        return CorrelatedFaultClient(turn, target)
    return ProtocolClient(turn, target, catalog)
