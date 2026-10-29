"""Local durable accounting; no credentials, clients, prompts or result rows."""
from contextlib import contextmanager
from decimal import Decimal, InvalidOperation
import json
import os
from pathlib import Path
import time
from urllib.parse import urlsplit


class BudgetStopped(RuntimeError):
    """A fixed safe reason, never provider exception text."""


def atomic_json(path, value):
    path = Path(path)
    temporary = path.with_suffix(path.suffix + '.tmp')
    with temporary.open('w', encoding='utf-8', newline='\n') as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write('\n'); stream.flush(); os.fsync(stream.fileno())
    os.replace(temporary, path)


@contextmanager
def run_lock(directory):
    """OS releases the advisory lock on process death; no stale-PID guessing."""
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    with (directory / 'run.lock').open('a+b') as stream:
        stream.seek(0, 2)
        if not stream.tell():
            stream.write(b'0'); stream.flush()
        stream.seek(0)
        try:
            if os.name == 'nt':
                import msvcrt
                msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            raise ValueError('Evaluation directory is already in use') from None
        try:
            yield
        finally:
            stream.seek(0)
            if os.name == 'nt':
                msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(stream.fileno(), fcntl.LOCK_UN)


class Journal:
    def __init__(self, directory, manifest, *, resume=False):
        self.path = Path(directory) / 'journal.json'
        if self.path.exists():
            if not resume:
                raise ValueError('First-attempt output already exists; use reviewed resume or a new directory')
            self.data = json.loads(self.path.read_text(encoding='utf-8'))
            if self.data.get('manifest') != manifest:
                raise ValueError('Resume configuration or source changed')
        else:
            if resume:
                raise ValueError('No evaluation checkpoint to resume')
            self.data = {'version': 1, 'manifest': manifest, 'started_at': time.time(),
                         'results': [], 'active': None, 'budget': None, 'interrupted': False,
                         'runner_reason': None}
            self.save()

    def save(self):
        atomic_json(self.path, self.data)

    def begin(self, case):
        self.data['active'] = {'id': case['id'], 'cohort': case['cohort'],
                               'domain': case['domain'], 'tags': case['tags'],
                               'planned_turns': len(case['turns']), 'turns': []}
        if case.get('host_version'):
            self.data['active']['host_version'] = case['host_version']
        self.save()

    def turn(self, result):
        self.data['active']['turns'].append(result)
        self.save()

    def finish(self, result):
        self.data['results'].append(result)
        self.data['active'] = None
        self.save()

    def abandon_active(self):
        active = self.data['active']
        if active:
            planned = active.pop('planned_turns')
            complete = len(active['turns']) == planned
            active.update(correct=complete and all(t['correct'] for t in active['turns']), interrupted=True,
                          first_failing_turn=next((t['index'] for t in active['turns'] if not t['correct']),
                                                  None if complete else len(active['turns']) + 1),
                          unexecuted_turns=planned - len(active['turns']))
            self.finish(active)


def _money(value):
    try:
        amount = Decimal(str(value))
        if not amount.is_finite() or amount < 0:
            raise ValueError
        return amount
    except (InvalidOperation, ValueError):
        raise ValueError('Invalid reviewed monetary amount') from None


def validate_approval(approval, configuration, directory, *, accounting_mode='strict'):
    """Operator attestations are necessary; they do not independently verify a vendor."""
    required = {'authorized', 'authorization_id', 'synthetic_only', 'configuration', 'output_directory',
                'max_requests', 'max_input_tokens', 'max_output_tokens', 'max_total_tokens', 'max_seconds',
                'max_cost_usd', 'per_call_output_tokens', 'pricing', 'accounting'}
    exploratory = accounting_mode == 'exploratory'
    if accounting_mode not in ('strict', 'exploratory'):
        raise ValueError('Unknown accounting mode')
    if exploratory:
        required |= {'accounting_mode', 'accepts_billing_uncertainty', 'call_timeout_seconds',
                     'turn_timeout_seconds', 'capture_responses'}
    if (not isinstance(approval, dict) or set(approval) != required or approval['authorized'] is not True
            or approval['synthetic_only'] is not True or not isinstance(approval['authorization_id'], str)
            or not approval['authorization_id'].strip() or len(approval['authorization_id']) > 200
            or approval['configuration'] != configuration
            or approval['output_directory'] != str(Path(directory).resolve())):
        raise ValueError('Exact evaluation approval is missing or does not match')
    if exploratory:
        if (approval['accounting_mode'] != 'exploratory'
                or approval['accepts_billing_uncertainty'] is not True
                or type(approval['capture_responses']) is not bool):
            raise ValueError('Explicit exploratory billing uncertainty acceptance is required')
        for key in ('call_timeout_seconds', 'turn_timeout_seconds'):
            if type(approval[key]) is not int or not 1 <= approval[key] <= 600:
                raise ValueError('Finite exploratory timeouts are required')
        if approval['call_timeout_seconds'] > approval['turn_timeout_seconds']:
            raise ValueError('Call timeout exceeds turn timeout')
    endpoint = urlsplit(configuration['endpoint'])
    if (endpoint.scheme != 'https' or not endpoint.hostname or endpoint.username or endpoint.password
            or endpoint.query or endpoint.fragment):
        raise ValueError('A reviewed HTTPS endpoint without embedded credentials is required')
    if (configuration['adapter'] != 'sdk_chat_completions' or not isinstance(configuration['model'], str)
            or not configuration['model'].strip() or len(configuration['model']) > 200):
        raise ValueError('Unsupported evaluation transport')
    for key in ('max_requests', 'max_input_tokens', 'max_output_tokens', 'max_total_tokens', 'max_seconds',
                'per_call_output_tokens'):
        if type(approval[key]) is not int or not 0 < approval[key] <= 10**9:
            raise ValueError('Positive bounded evaluation limits are required')
    if approval['max_requests'] > 10000 or not 256 <= approval['per_call_output_tokens'] <= 16384:
        raise ValueError('Evaluation request/output limits are too large')
    if not _money(approval['max_cost_usd']):
        raise ValueError('A positive monetary ceiling is required')
    pricing = approval['pricing']
    date_key = 'observed_date' if exploratory else 'effective_date'
    extra_models = set(configuration.get('stage_models', {}).values()) - {configuration['model']}
    if (not isinstance(pricing, dict) or set(pricing) != {'reviewed', 'source_url', date_key,
            'verified_at', 'units', 'input_usd_per_million', 'output_usd_per_million'}
            | ({'models'} if extra_models else set())
            or pricing['reviewed'] is not True or pricing['units'] != 'USD_per_million_tokens'
            or not isinstance(pricing['source_url'], str) or not pricing['source_url'].startswith('https://')):
        raise ValueError('Reviewed pricing provenance and units are required')
    from datetime import date, datetime
    price_url = urlsplit(pricing['source_url'])
    if not price_url.hostname or price_url.username or price_url.password or price_url.query or price_url.fragment:
        raise ValueError('Pricing provenance cannot contain credentials or query parameters')
    try:
        date.fromisoformat(pricing[date_key])
        stamp = datetime.fromisoformat(pricing['verified_at'])
        if stamp.tzinfo is None:
            raise ValueError
    except (ValueError, TypeError):
        raise ValueError('Dated pricing verification is required') from None
    _money(pricing['input_usd_per_million']); _money(pricing['output_usd_per_million'])
    if extra_models:
        # Every additional stage model needs its own reviewed rate; none is inferred.
        models = pricing['models']
        if (not isinstance(models, dict) or set(models) != extra_models or any(
                not isinstance(rate, dict) or set(rate) != {'source_url', 'input_usd_per_million', 'output_usd_per_million'}
                or not isinstance(rate['source_url'], str) or not rate['source_url'].startswith('https://')
                for rate in models.values())):
            raise ValueError('Reviewed pricing is required for every stage model')
        for rate in models.values():
            _money(rate['input_usd_per_million']); _money(rate['output_usd_per_million'])
    accounting = approval['accounting']
    if exploratory:
        if (not isinstance(accounting, dict) or set(accounting) != {'input_estimate', 'overhead_tokens',
                'guaranteed_bound', 'provider_billing_verified'}
                or accounting['input_estimate'] != 'serialized_utf8_bytes_plus_overhead'
                or accounting['guaranteed_bound'] is not False
                or accounting['provider_billing_verified'] is not False
                or type(accounting['overhead_tokens']) is not int
                or not 0 <= accounting['overhead_tokens'] <= 1000000):
            raise ValueError('Exploratory estimates must not claim billing guarantees')
        return
    if (not isinstance(accounting, dict) or set(accounting) != {'reviewed', 'input_bound', 'overhead_tokens',
            'output_cap_includes_reasoning', 'usage_includes_reasoning', 'no_unpriced_fees'}
            or accounting['reviewed'] is not True or accounting['input_bound'] != 'serialized_utf8_bytes_plus_overhead'
            or any(accounting[k] is not True for k in ('output_cap_includes_reasoning', 'usage_includes_reasoning', 'no_unpriced_fees'))
            or type(accounting['overhead_tokens']) is not int or not 0 <= accounting['overhead_tokens'] <= 1000000):
        raise ValueError('Insufficient provider accounting evidence; live dispatch prohibited')


def usage_metadata(response):
    """Chat Completions adapter: details are subsets of input/output, not extra tokens."""
    usage = getattr(response, 'usage', None)
    if usage is None:
        return None
    def get(value, name):
        return value.get(name) if isinstance(value, dict) else getattr(value, name, None)
    inp, out = get(usage, 'prompt_tokens'), get(usage, 'completion_tokens')
    total = get(usage, 'total_tokens')
    if (any(type(v) is not int or v < 0 for v in (inp, out))
            or (total is not None and (type(total) is not int or total != inp + out))):
        raise ValueError('Invalid provider usage')
    cached = get(get(usage, 'prompt_tokens_details'), 'cached_tokens')
    reasoning = get(get(usage, 'completion_tokens_details'), 'reasoning_tokens')
    for value, bound in ((cached, inp), (reasoning, out)):
        if value is not None and (type(value) is not int or not 0 <= value <= bound):
            raise ValueError('Invalid provider usage detail')
    return {'input': inp, 'output': out, 'total': inp + out,
            'cached_input': cached, 'reasoning': reasoning}


class Budget:
    def __init__(self, approval, journal, *, clock=time.time, stop_on_transport_failure=True):
        self.approval, self.journal, self.clock = approval, journal, clock
        # When False, an uncertain call keeps its full reservation in every
        # limit; the failed turn is scored and later turns may still run.
        self.stop_on_transport_failure = stop_on_transport_failure
        self.input_price = _money(approval['pricing']['input_usd_per_million'])
        self.output_price = _money(approval['pricing']['output_usd_per_million'])
        # Approved models only: the configured model plus reviewed stage models.
        self.prices = {approval['configuration']['model']: (self.input_price, self.output_price),
                       **{model: (_money(rate['input_usd_per_million']), _money(rate['output_usd_per_million']))
                          for model, rate in approval['pricing'].get('models', {}).items()}}
        if journal.data['budget'] is None:
            journal.data['budget'] = {'calls': [], 'stop_reason': None}
            journal.save()
        self.state = journal.data['budget']

    @property
    def exploratory(self):
        return self.approval.get('accounting_mode') == 'exploratory'

    @property
    def exhausted(self):
        if not self.state['stop_reason']:
            used = self.accounting()
            reason = ('time_budget' if self.remaining_seconds() <= 0 else
                      'request_budget' if used['requests_dispatched'] >= self.approval['max_requests'] else
                      'input_budget' if used['input_charged_or_reserved'] >= self.approval['max_input_tokens'] else
                      'output_budget' if used['output_charged_or_reserved'] >= self.approval['max_output_tokens'] else
                      'total_token_budget' if used['input_charged_or_reserved'] + used['output_charged_or_reserved'] >= self.approval['max_total_tokens'] else
                      'cost_budget' if Decimal(used['estimated_usd_charged_or_reserved']) >= _money(self.approval['max_cost_usd']) else None)
            if reason:
                self.state['stop_reason'] = reason
                self.journal.save()
        return self.state['stop_reason'] is not None

    def remaining_seconds(self):
        elapsed = self.clock() - self.journal.data['started_at']
        return self.approval['max_seconds'] - elapsed if elapsed >= 0 else 0

    def accounting(self):
        calls = self.state['calls']
        return {'accounting_mode': 'exploratory' if self.exploratory else 'strict',
                'requests_dispatched': len(calls),
                'input_charged_or_reserved': sum(c['input'] for c in calls),
                'output_charged_or_reserved': sum(c['output'] for c in calls),
                'estimated_usd_charged_or_reserved': str(sum((Decimal(c['cost']) for c in calls), Decimal(0))),
                'uncertain_requests': sum(c['status'] in (
                    ('reserved', 'failed', 'usage_unavailable') if self.exploratory else ('reserved',)) for c in calls),
                'stop_reason': self.state['stop_reason'],
                'provider_billed_usd': None}

    def stop(self, reason):
        self.state['stop_reason'] = reason
        self.journal.save()
        raise BudgetStopped(reason)

    def reserve(self, options):
        if self.exhausted:
            self.stop(self.state['stop_reason'] or 'time_budget')
        model = options.get('model')
        if model not in self.prices:
            self.stop('model_changed')
        input_price, output_price = self.prices[model]
        out = options.get('max_completion_tokens')
        if type(out) is not int or not 0 < out <= self.approval['per_call_output_tokens']:
            self.stop('output_cap')
        # Include instructions, metadata, conversation, schema and framing options.
        inp = len(json.dumps(options, ensure_ascii=False, allow_nan=False).encode('utf-8')) + self.approval['accounting']['overhead_tokens']
        cost = (inp * input_price + out * output_price) / 1000000
        used = self.accounting()
        if used['requests_dispatched'] >= self.approval['max_requests']:
            self.stop('request_budget')
        if used['input_charged_or_reserved'] + inp > self.approval['max_input_tokens']:
            self.stop('input_budget')
        if used['output_charged_or_reserved'] + out > self.approval['max_output_tokens']:
            self.stop('output_budget')
        if used['input_charged_or_reserved'] + used['output_charged_or_reserved'] + inp + out > self.approval['max_total_tokens']:
            self.stop('total_token_budget')
        if Decimal(used['estimated_usd_charged_or_reserved']) + cost > _money(self.approval['max_cost_usd']):
            self.stop('cost_budget')
        stage = {'sageql_report_intent': 'intent', 'sageql_report_interpretation': 'planning',
                 'sageql_report_review': 'review'}.get(options.get('response_format', {}).get('json_schema', {}).get('name'), 'unknown')
        self.state['calls'].append({'stage': stage, 'input': inp, 'output': out, 'cost': str(cost), 'status': 'reserved',
                                    **({'model': model} if len(self.prices) > 1 else {})})
        if self.exploratory:
            self.state['calls'][-1].update(estimated_input=inp, requested_output_cap=out)
        self.journal.save()  # Must succeed before the external call is attempted.
        options['timeout'] = min(options.get('timeout', 30), max(.001, self.remaining_seconds()))
        return len(self.state['calls']) - 1

    def settle(self, ticket, usage, *, failed=False, invalid=False):
        call = self.state['calls'][ticket]
        if usage is not None:
            if (not self.exploratory and usage['input'] > call['input']) or usage['output'] > call['output']:
                self.state['stop_reason'] = 'provider_bound_violation'
            input_price, output_price = self.prices[call.get('model', self.approval['configuration']['model'])]
            call.update(input=usage['input'], output=usage['output'],
                        cost=str((usage['input'] * input_price + usage['output'] * output_price) / 1000000))
        if invalid:
            self.state['stop_reason'] = 'invalid_usage'
        elif self.exploratory and (failed or usage is None) and self.stop_on_transport_failure:
            self.state['stop_reason'] = 'transport_failure' if failed else 'missing_usage'
        call['status'] = 'failed' if failed else 'observed' if usage is not None else 'usage_unavailable'
        self.journal.save()
        if self.exploratory:
            self.exhausted  # Reconcile actual aggregate usage before another dispatch.

    def capture_response(self, ticket, response, usage):
        """Opt-in local synthetic visible output only; never headers or exception bodies."""
        if not self.exploratory or not self.approval['capture_responses']:
            return
        try:
            choice = response.choices[0]
            content = choice.message.content
            if content is not None and (not isinstance(content, str) or len(content) > 128000):
                raise ValueError('Response exceeds local recording bound')
            value = {'call': ticket + 1, 'stage': self.state['calls'][ticket]['stage'],
                     'content': content, 'finish_reason': choice.finish_reason,
                     'usage': usage}
            directory = self.journal.path.parent / 'responses'
            directory.mkdir(exist_ok=True)
            atomic_json(directory / f'call-{ticket + 1:04d}.json', value)
        except Exception:
            self.state['stop_reason'] = 'response_recording_failure'
            self.journal.save()
            raise
