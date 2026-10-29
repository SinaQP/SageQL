"""Host-registered measure choices, checked without accepting assistant evidence."""

from dataclasses import replace
import re

from sageql.conversation import Message
from sageql.sdk.intent import ConceptRef, ReportIntent
from sageql.sdk.models import EntityLabelDimension, Interpretation, MetricDefinition, ReportingCatalog, ReportSpec
from sageql.sdk.phrases import ScopedText, concept_evidence, words as _words, GENERIC_MEANS


def _participant_mean_requested(metric: MetricDefinition, evidence: list[str]) -> bool:
    for value in reversed(evidence):
        scoped = ScopedText(value)
        if any(match.polarity == "negative" for term in (metric.label, *metric.selection_terms, *GENERIC_MEANS)
               for match in scoped.literal(term)):
            return False
        if any(match.polarity == "positive" for term in (metric.label, *metric.selection_terms)
               for match in scoped.literal(term)):
            return True
    return False


def participant_mean_context(intent: ReportIntent, messages: tuple[Message, ...],
                             catalog: ReportingCatalog, current_spec: ReportSpec | None) -> ReportIntent:
    """Retain a uniquely registered participant mean requested in user words.

    Columns are compared locally; this never creates a formula, joins sources or
    infers access. Unrecognized/ambiguous vocabulary keeps ordinary agent review.
    """
    users = [item.content for item in messages if item.role == "user"]
    evidence = users if intent.turn_kind == "answer" else users[-1:]
    identifiers = {ref.dataset_id for ref in intent.metrics} or {ref.dataset_id for ref in intent.dimensions}
    if len(identifiers) != 1:
        return intent
    dataset = next(item for item in catalog.datasets if item.id == next(iter(identifiers)))
    requested_refs = concept_evidence(" ".join(evidence), catalog).positive
    requested = [metric for metric in dataset.metrics if metric.aggregation == "sum_per_participant"
                 and (dataset.id, metric.id) in requested_refs and _participant_mean_requested(metric, evidence)]
    if len(requested) != 1:
        return intent
    selected = requested[0]
    def explicit_average(metric):
        return (dataset.id, metric.id) in requested_refs

    removed_ids = {metric.id for metric in dataset.metrics if metric.aggregation == "average"
                   and metric.column == selected.column and not explicit_average(metric)}
    metrics = tuple(ref for ref in intent.metrics if ref.concept_id not in removed_ids)
    ref = ConceptRef(dataset.id, selected.id)
    if ref not in metrics:
        metrics += (ref,)
    changes = {"metrics": metrics}
    if intent.order_by in removed_ids:
        changes["order_by"] = selected.id
    from sageql.sdk.evidence import request_evidence
    temporal = request_evidence(messages, catalog, current_spec).time_grain not in {None, "none"}
    if intent.turn_kind == "new" and not temporal:
        changes["time_grain"] = "none"
    return replace(intent, **changes)


def explicit_measure_missing(intent: ReportIntent, messages: tuple[Message, ...],
                             current_spec: ReportSpec | None, catalog: ReportingCatalog) -> bool:
    """Restricted measures need a host-declared phrase in the user's own request.

    This is a conservative vocabulary guard, not a general proof of NL intent.
    Refinements may preserve an explicitly selected existing measure. Assistant
    suggestions cannot grant a measure; new requests do not inherit old evidence.
    """
    users = [item.content for item in messages if item.role == "user"]
    evidence = users if intent.turn_kind == "answer" else users[-1:]
    selected = concept_evidence(" ".join(evidence), catalog)
    for ref in intent.metrics:
        dataset = next(item for item in catalog.datasets if item.id == ref.dataset_id)
        metric = next(item for item in dataset.metrics if item.id == ref.concept_id)
        terms = metric.selection_terms
        ranking = intent.order_by == metric.id and intent.limit is not None and intent.limit < 100
        if not terms and ranking:
            terms = metric.ranking_terms
        if not terms:
            continue
        if (ref.dataset_id, ref.concept_id) in selected.negative:
            return True
        if (ref.dataset_id, ref.concept_id) in selected.positive:
            continue
        if (intent.turn_kind == "refine" and current_spec is not None
                and current_spec.dataset_id == ref.dataset_id and ref.concept_id in current_spec.metric_ids):
            continue
        if metric.aggregation == "sum_per_participant":
            if not _participant_mean_requested(metric, evidence):
                return True
            continue
        if not any(match.polarity == "positive" for term in (metric.label, *terms)
                   for text in evidence for match in ScopedText(text).literal(term)):
            return True
    return False


def measure_question(catalog: ReportingCatalog, language: str = "fa") -> Interpretation:
    labels = [metric.label for dataset in catalog.datasets for metric in dataset.metrics
              if (not dataset.default_metric_ids or metric.id in dataset.default_metric_ids)
              and not metric.selection_terms]
    choices = (" یا " if language == "fa" else " or ").join(list(dict.fromkeys(labels))[:3])
    question = (f"کدام معیار گزارش را می‌خواهید{': ' + choices if choices else ''}؟"
                if language == "fa" else
                f"Which report measure should I use{': ' + choices if choices else ''}?")
    return Interpretation("needs_clarification", question=question,
                          clarification_key="explicit_measure", continues_clarification=False)


def capability_reply(catalog: ReportingCatalog, language: str = "fa") -> Interpretation | None:
    datasets = [item for item in catalog.datasets if item.default_metric_ids]
    if not datasets:
        return None
    reports = []
    separator = "، " if language == "fa" else ", "
    for dataset in datasets[:2]:
        measures = separator.join([m.label for m in dataset.metrics if m.id in dataset.default_metric_ids][:2])
        labels = {d.column for d in dataset.dimensions if isinstance(d, EntityLabelDimension)}
        groups = separator.join([d.label for d in dataset.dimensions
                                 if isinstance(d, EntityLabelDimension) or d.column not in labels][:4])
        reports.append(measures + ((" به تفکیک " if language == "fa" else " by ") + groups if groups else ""))
    question = ("سلام! می‌توانم گزارش «" + "؛ ".join(reports)
                + "» تهیه کنم، دوره‌ها را مقایسه کنم و جدول یا نمودار بدهم. "
                + ("تاریخ‌های شمسی هم پشتیبانی می‌شوند. " if catalog.preferred_calendar == "jalali" else "")
                + "چه گزارشی نیاز دارید؟"
                if language == "fa" else
                "I can report " + "; ".join(reports) + ", compare periods and create tables or charts. Which report would help you?")
    return Interpretation("needs_clarification", question=question, clarification_key="request")


def capability_request(messages: tuple[Message, ...]) -> bool:
    """Recognize questions addressed to the assistant's reporting abilities.

    Do not match questions about facts in the application's data. Unrecognized
    questions still use normal interpretation; this shortcut executes no data.
    """
    latest = next((item.content for item in reversed(messages) if item.role == "user"), "")
    text = _words(latest).strip(" !؟?.,،")
    if text in {"سلام", "سلام خوبی", "hello", "hi"}:
        return True
    subject = any(term in text for term in ("چه کار", "چه گزارش", "چه قابلیت", "چی کار", "چیکار", "what can you do"))
    ability = any(term in text for term in ("می تونی", "میتونی", "می توانی", "میتوانی", "می توانید", "میتوانید", "what can you do"))
    return subject and ability


def ambiguous_ranking_request(messages: tuple[Message, ...], current_spec: ReportSpec | None,
                              catalog: ReportingCatalog) -> bool:
    """A fresh quality ranking cannot acquire a metric merely from availability."""
    if current_spec is not None:
        return False
    latest = _words(next((item.content for item in reversed(messages) if item.role == "user"), ""))
    def mentions(term):
        return re.search(r"(?<!\w)" + re.escape(_words(term)) + r"(?!\w)", latest) is not None
    if not any(mentions(term) for term in catalog.ambiguous_ranking_terms):
        return False
    return not any(mentions(term) for dataset in catalog.datasets for metric in dataset.metrics
                   for term in (*metric.selection_terms, *metric.ranking_terms))
