"""Conservative request evidence independent of model agreement and database data.

This is a bounded fa/en recognizer, not a general natural-language parser. It
anchors unambiguous whole named months, comparison order and explicit grouping.
Unrecognized wording still needs semantic interpretation/review. Only user
messages are evidence; assistant suggestions never supply a year or requirement.
"""

from dataclasses import dataclass, replace
from datetime import date, timedelta
import re

from sageql.conversation import Message
from sageql.sdk.calendars import JALALI_MONTH_NAMES, jalali_month_bounds
from sageql.sdk.models import Interpretation, PeriodSelection, ReportingCatalog, ReportSpec, SDKError, UserFilter
from sageql.sdk.phrases import GENERIC_MEANS, GRAIN_PHRASES, ScopedText, concept_evidence, grouping_evidence, words
from sageql.sdk.grounding import FilterRequirement, OrderingRequirement, controls, conflicting_filters


_GREGORIAN = ("january", "february", "march", "april", "may", "june", "july", "august",
              "september", "october", "november", "december")
_GREGORIAN_FA = ("ژانویه", "فوریه", "مارس", "آوریل", "مه", "ژوئن", "ژوئیه", "اوت",
                 "سپتامبر", "اکتبر", "نوامبر", "دسامبر")
_JALALI_EN = ("farvardin", "ordibehesht", "khordad", "tir", "mordad", "shahrivar",
              "mehr", "aban", "azar", "dey", "bahman", "esfand")
_MONTHS = {name: (calendar, index) for names, calendar in (
    (JALALI_MONTH_NAMES, "jalali"), (_JALALI_EN, "jalali"),
    (_GREGORIAN, "gregorian"), (_GREGORIAN_FA, "gregorian"))
    for index, name in enumerate(names, 1)}
_MONTH_PATTERN = re.compile(r"(?<!\w)(?:" + "|".join(map(re.escape, _MONTHS)) + r")(?!\w)")
_COMPARISON = re.compile(r"نسبت به|در مقایسه|مقایسه.{0,45}(?:با|و)|"
                         r"\bcompare\b.{0,100}\b(?:with|and|to)\b|"
                         r"\b(?:versus|vs\.?|compared (?:with|to)|against)\b")

OPERATION_LABELS = {
    "percentage_share": ("سهم از کل", "shares of a total"),
    "absence": ("یافتن موجودیت‌های بدون رکورد مرتبط", "entities without related records"),
    "partitioned_ranking": ("رتبه‌بندی جداگانه در هر گروه", "ranking separately within each group"),
    "series_extrema": ("محاسبهٔ بیشینه و کمینهٔ سری زمانی", "computed time-series extrema"),
    "formula": ("محاسبهٔ ثبت‌نشده", "an unregistered calculation"),
    "other": ("عملیات ثبت‌نشده", "an unregistered operation"),
    "multiple_periods": ("مقایسهٔ بیش از دو دوره", "comparison of more than two periods"),
}


@dataclass(frozen=True)
class UnsupportedRequirement:
    """An unavailable operation and a literal quotation from the user's request.

    A model cannot register a capability using this ledger. It records negative
    requirements that would otherwise disappear from the executable ReportSpec.
    """

    operation: str
    evidence: str


def unsupported_message(operations: tuple[str, ...], language: str) -> str:
    labels = [OPERATION_LABELS[item][0 if language == "fa" else 1] for item in dict.fromkeys(operations)]
    if language == "fa":
        return ("درخواست شامل «" + "، ".join(labels) + "» است که در قابلیت‌های فعلی گزارش ثبت نشده است. "
                "برای گزارش کامل، میزبان باید این قابلیت را ثبت کند؛ یا درخواست را بدون این بخش مطرح کنید.")
    return ("This request includes " + ", ".join(labels) + ", which the current reporting contract does not support. "
            "The host must register that capability for a complete report, or you can request a report without that part.")


_OPERATIONS = {
    "percentage_share": r"سهم.{0,70}(?:از کل|کل ساعات|کل مجموع)|درصد سهم|"
        r"\b(?:percentage|percent|proportion|share)s?\b.{0,55}\b(?:of (?:the )?(?:total|all)|of each|share)\b|"
        r"\bshares? (?:of|in)\s+(?:the\s+)?\w+",
    "absence": r"هیچ.{0,65}(?:ثبت نکرد|نداشته|انجام نداده)|"
        r"\b(?:without any|with no)\b.{0,50}\b(?:records?|events?|facts?|rows?|data)\b|"
        r"\b(?:never|no)\b.{0,35}\brecorded\b",
    "partitioned_ranking": r"\b(?:top|highest|largest|primary)\b.{0,35}\b(?:within|for|per) each\b|"
        r"\bfor each\b.{0,75}\b(?:top|highest|primary)\b|"
        r"برای هر\s+\w+.{0,45}(?:برترین|اولین|بالاترین)",
    "formula": r"\b(?:unsupported|unregistered|arbitrary)\s+(?:ratio|formula|calculation)\b|"
        r"(?:نسبت|فرمول|محاسبه)\s+(?:دیگر\s+)?ثبت نشده",
}


def _operation_mentions(text: str, protected=()) -> tuple[tuple[str, ...], bool]:
    scoped = ScopedText(text)
    visible = scoped.masked(protected)
    patterns = dict(_OPERATIONS)
    if re.search(r"بیشترین|highest|most", visible) and re.search(r"کمترین|lowest|least", visible):
        patterns["series_extrema"] = (r"کدام (?:ماه|روز|هفته).{0,100}(?:بیشترین|کمترین)|"
                                      r"\bwhich (?:month|day|week)\b.{0,100}\b(?:highest|lowest|most|least)\b")
    result, unresolved = [], False
    for operation, pattern in patterns.items():
        compiled = re.compile(pattern)
        for start, end in scoped.clauses():
            for match in compiled.finditer(visible, start, end):
                polarity = scoped.polarity(*match.span())
                if polarity == "positive":
                    result.append(operation)
                elif polarity == "unresolved":
                    unresolved = True
    return tuple(dict.fromkeys(result)), unresolved


def operation_evidence(text: str) -> tuple[str, ...]:
    """Positive scoped operations only; exclusion never erases another clause."""
    return _operation_mentions(text)[0]


def requirement_state(requirement: UnsupportedRequirement, texts: list[str], catalog: ReportingCatalog,
                      quoted_role: str | None = None) -> str:
    """Validate literal ledger evidence in its original user scope, latest first.

    A model's ledger cannot turn an excluded operation or registered name into
    an active requirement. Unknown positive wording retains the original typed
    ledger behavior; invented evidence remains an unrepaired shape error.
    """
    quote = words(requirement.evidence)
    for text in reversed(texts):
        scoped = ScopedText(text)
        occurrences = tuple(re.finditer(re.escape(quote), scoped.text))
        if not occurrences:
            continue
        protected = concept_evidence(text, catalog).spans
        if any(definition.value_vocabulary for dataset in catalog.datasets for definition in dataset.filters):
            # Registered predicate operands are data, even when their terms
            # resemble unavailable analytics. Other clauses stay independently
            # positive; a value mapping cannot register an operation.
            protected = (*protected, *controls(text, catalog).spans)
        pattern = _OPERATIONS.get(requirement.operation)
        operations = tuple(match for start, end in scoped.clauses()
                           for match in re.compile(pattern).finditer(scoped.text, start, end)) if pattern else ()
        states = []
        for occurrence in occurrences:
            related = [match for match in operations if match.start() < occurrence.end() and occurrence.start() < match.end()]
            for match in related or (occurrence,):
                states.append("literal" if any(a <= match.start() and match.end() <= b for a, b in protected)
                              else scoped.polarity(*match.span()))
        if "positive" in states:
            return "positive"
        if "unresolved" in states:
            return "positive" if quoted_role == "positive" else "excluded" if quoted_role == "literal" else "unresolved"
        return "excluded"
    raise SDKError("invalid_interpretation", "Requirement evidence is not in the user request.",
                   stage="intent", reason="requirements")


@dataclass(frozen=True)
class _ProjectionRequirement:
    """A complete business projection; empty is distinct from unspecified."""

    dataset_id: str
    dimension_ids: tuple[str, ...] = ()


@dataclass(frozen=True)
class RequestEvidence:
    # An explicit reset establishes fresh control defaults, including while
    # its missing details are resolved over subsequent clarification turns.
    new_report: bool = False
    unresolved: tuple[tuple[str, str], ...] = ()
    dimension_choices: tuple[tuple[tuple[str, str], ...], ...] = ()
    filters_complete: bool = False
    metric_selection_complete: bool = False
    period: PeriodSelection | None = None
    comparison: PeriodSelection | None = None
    comparison_specified: bool = False
    time_grain: str | None = None
    plain_table: bool = False
    missing: str | None = None
    operations: tuple[str, ...] = ()
    metrics: tuple[tuple[str, str], ...] = ()
    forbidden_grains: tuple[str, ...] = ()
    excluded_metrics: tuple[tuple[str, str], ...] = ()
    excluded_dimensions: tuple[tuple[str, str], ...] = ()
    excluded_filters: tuple[tuple[str, str], ...] = ()
    clarification: str | None = None
    quoted_role: str | None = None
    dimensions: tuple[tuple[str, str], ...] = ()
    retained_filters: tuple[UserFilter, ...] = ()
    # Local effective requirements; values never enter observation diagnostics.
    filter_requirements: tuple[FilterRequirement, ...] = ()
    ordering: OrderingRequirement | None = None
    pending_filter_value: tuple[str, str] | None = None
    pending_filter: tuple[str, str, str] | None = None
    confirmed_clarification_answer: bool = False
    clarified_table_defaults: bool = False
    projection: _ProjectionRequirement | None = None
    grouping_requested: bool = False


def _metric_evidence(text: str, catalog: ReportingCatalog) -> tuple[tuple[str, str], ...]:
    """Exact, unambiguous host labels supplement fallible metric extraction.

    Longest overlapping labels win (e.g. average revenue vs revenue). Predicates
    and explicit removals are not output requirements. Synonyms still belong to
    semantic interpretation, not a core dictionary of business measures.
    """
    return concept_evidence(text, catalog).positive


_YEAR_ANSWER = re.compile(r"(?:سال\s+)?[0-9]{4}(?:\s+(?:شمسی|میلادی))?[.!]?")


def year_answer(text: str) -> str | None:
    """One affirmative year with bounded polite wrappers, never a question/guess."""
    from sageql.sdk.phrases import clarification_literal, question_spans
    scoped = ScopedText(text)
    if question_spans(scoped):
        return None
    values = []
    polite = {'please', 'thanks', 'thank you', 'لطفا', 'لطفاً', 'ممنون'}
    for start, end in scoped.clauses():
        clause = scoped.surface(start, end).strip()
        if not clause or words(clause).strip(' .!') in polite:
            continue
        literal = clarification_literal(clause)
        if literal is None:
            return None
        value = re.sub(r'\s+(?:please|لطفا|لطفاً)$', '', words(literal).strip(' .!'))
        if not _YEAR_ANSWER.fullmatch(value):
            return None
        values.append(value)
    return values[0] if values and len(set(values)) == 1 else None


def _user_text(messages: tuple[Message, ...]) -> str:
    users = [item.content for item in messages if item.role == "user"]
    latest = users[-1] if users else ""
    # A year-only clarification can complete the immediately preceding user's
    # named period. Never borrow a year from the assistant or business clock.
    supplied_year = year_answer(latest)
    if supplied_year is not None and len(users) > 1:
        return users[-2] + " " + supplied_year
    return latest


def _numeric_period(text: str) -> tuple[PeriodSelection | None, str | None]:
    """Anchor date-only literals with explicit endpoint semantics.

    Gregorian 'to' alone is deliberately not interpreted as inclusive/exclusive.
    Persian date ranges follow the registered inclusive Jalali contract. Other
    calendars and ambiguous endpoints stay with clarification/semantic review.
    """
    matches = list(re.finditer(r"(?<![0-9])[0-9]{4}[-/][0-9]{2}[-/][0-9]{2}(?![0-9])", text))
    if not 1 <= len(matches) <= 2:
        return None, None
    dates = [item.group().replace("/", "-") for item in matches]
    jalali = "شمسی" in text or "جلالی" in text or "jalali" in text
    gregorian = "میلادی" in text or "gregorian" in text
    if (jalali and gregorian) or (not jalali and not gregorian and any(int(item[:4]) < 1600 for item in dates)):
        return None, "calendar"
    if len(dates) == 1:
        prefix = text[max(0, matches[0].start() - 12):matches[0].start()]
        if not re.search(r"\b(?:on|dated)\s*$|(?:روز|تاریخ)\s*$", prefix):
            return None, None
        if jalali:
            try:
                from sageql.sdk.calendars import jalali_to_gregorian
                jalali_to_gregorian(*map(int, dates[0].split("-")))
                return PeriodSelection("jalali_range", dates[0], dates[0]), None
            except ValueError:
                return None, "period"
        try:
            return PeriodSelection("range", dates[0], (date.fromisoformat(dates[0]) + timedelta(days=1)).isoformat()), None
        except ValueError:
            return None, "period"
    between = text[matches[0].end():matches[1].start()]
    exclusive = re.search(r"\bbefore\b|تا پیش از", between) or "exclusive" in text
    inclusive = re.search(r"\bthrough\b|\binclusive\b|با احتساب", text)
    if jalali and not exclusive:
        try:
            from sageql.sdk.calendars import jalali_to_gregorian
            first, last = (jalali_to_gregorian(*map(int, item.split("-"))) for item in dates)
            if first > last:
                return None, "period"
            return PeriodSelection("jalali_range", *dates), None
        except ValueError:
            return None, "period"
    if not exclusive and not inclusive:
        return None, None
    try:
        if jalali:
            from sageql.sdk.calendars import jalali_to_gregorian
            start, end = (jalali_to_gregorian(*map(int, item.split("-"))) for item in dates)
        else:
            start, end = map(date.fromisoformat, dates)
        if inclusive and not exclusive:
            end += timedelta(days=1)
        if start >= end:
            return None, "period"
        return PeriodSelection("range", start.isoformat(), end.isoformat()), None
    except (ValueError, OverflowError):
        return None, "period"


def _period_missing(evidence: RequestEvidence, detail: str) -> RequestEvidence:
    """A missing date detail cannot overwrite another active question's role."""
    return replace(evidence, missing=evidence.missing or detail,
                   clarification=evidence.clarification or 'period_detail',
                   unresolved=tuple(dict.fromkeys((*evidence.unresolved, (detail, 'period_detail')))))


def _details(evidence: RequestEvidence) -> tuple[tuple[str, str], ...]:
    return evidence.unresolved or (((evidence.missing, evidence.clarification or 'period_detail'),)
                                   if evidence.missing else ())


def _period_roles(text, months, years):
    """Bind adjacent role/date operands before interpreting interval connectors.

    The same relation works in either order. A role assignment claims its
    connector even when incomplete or negative; it cannot become a range.
    """
    scoped = ScopedText(text)
    roles = tuple(re.finditer(r"\b(base|baseline|current|comparison|reference)(?:\s+(?:period|month))?\b", text))
    bindings = []
    for index, month in enumerate(months):
        start, end = month.span()
        before = [year for year in years if year.end() <= start and not text[year.end():start].strip()]
        after = [year for year in years if end <= year.start() and not text[end:year.start()].strip()]
        if after:
            end = after[0].end()
        elif before:
            start = before[-1].start()
        for role in roles:
            if role.end() <= start:
                gap = text[role.end():start]
                relation = re.fullmatch(r"\s+(?:(not)\s+)?(?:is|to|=)\s+(?:(not)\s+)?(?:the\s+)?", gap)
                span = (role.start(), end)
            elif end <= role.start():
                gap = text[end:role.start()]
                relation = re.fullmatch(r"\s+(?:is|as|be|=)\s+(?:(not)\s+)?(?:the\s+)?", gap)
                span = (start, role.end())
            else:
                continue
            if relation:
                polarity = 'negative' if any(relation.groups()) else scoped.polarity(*span)
                key = 'period' if role[1] in {'base', 'baseline', 'current'} else 'comparison'
                bindings.append((key, index, polarity))
    return tuple(dict.fromkeys(bindings))


_GROUPING_CUES = r'\b(?:by|for each|per|group\w*|breakdown)\b|به تفکیک|بر اساس|براساس'


def _total_projection(text, metrics, grouping, current_spec):
    scoped = ScopedText(text)
    groups = scoped.find(_GROUPING_CUES)
    requested = bool(grouping.positive or grouping.ambiguous or any(
        m.polarity in {'positive', 'unresolved'} for m in groups))
    owners = {owner for owner, _ in metrics.positive}
    tables = scoped.find(r'\b(?:table|tabulate)\b|(?<!\w)جدول(?!\w)')
    totals = scoped.find(r'\btotal(?:s)?\b|\b(?:whole|entire)\s+period\b|مجموع|جمع کل|کل\s+(?:بازه|دوره)')
    ranks = scoped.find(r'\b(?:sort\w*|order\w*|rank\w*|top|bottom|highest|lowest|largest|smallest|most|least|best|worst)\b|مرتب|رتبه|بیشترین|کمترین')
    if (current_spec is None and len(owners) == 1 and not requested
            and not any(m.polarity in {'positive', 'unresolved'} for m in ranks)
            and any(m.polarity == 'positive' for m in tables)
            and any(m.polarity == 'positive' for m in totals)):
        return _ProjectionRequirement(next(iter(owners))), requested
    return None, requested


def _current_evidence(messages: tuple[Message, ...], catalog: ReportingCatalog,
                      current_spec: ReportSpec | None = None) -> RequestEvidence:
    original = _user_text(messages)
    grounded = controls(original, catalog, current_spec)
    # Literal predicate values may themselves be metric labels, analytical
    # phrases or dates. Their role is data, never another reporting instruction.
    original = ScopedText(original).masked(grounded.spans)
    metrics = concept_evidence(original, catalog)
    scoped = ScopedText(original)
    generic_removal = any(match.polarity == "negative" and not any(
        a <= match.start and match.end <= b for a, b in metrics.spans)
        for term in GENERIC_MEANS for match in scoped.literal(term))
    if generic_removal:
        owners = {owner for owner, _ in metrics.positive}
        candidates = tuple((dataset.id, metric.id) for dataset in catalog.datasets
                           if not owners or dataset.id in owners
                           for metric in dataset.metrics if metric.aggregation in {"average", "sum_per_participant"})
        inherited = tuple(ref for ref in candidates if current_spec is not None
                          and ref[0] == current_spec.dataset_id and ref[1] in current_spec.metric_ids)
        candidates = inherited or candidates
        if len(candidates) == 1:
            metrics = replace(metrics, negative=tuple(dict.fromkeys((*metrics.negative, *candidates))))
        elif candidates:
            metrics = replace(metrics, ambiguous=True)
    dimensions = concept_evidence(original, catalog, "dimensions")
    owners = {owner for owner, _ in metrics.positive}
    if not owners and current_spec is not None:
        owners = {current_spec.dataset_id}
    grouping = grouping_evidence(original, catalog, owners)
    filters = concept_evidence(original, catalog, "filters")
    retained_filters = []
    if current_spec is not None:
        dataset = next((d for d in catalog.datasets if d.id == current_spec.dataset_id), None)
        definitions = {f.id: f for f in dataset.filters} if dataset else {}
        for condition in current_spec.filters:
            definition = definitions.get(condition.filter_id)
            if definition is None:
                continue
            for match in scoped.literal(definition.label):
                prefix, suffix = scoped.context(match.start, match.end)
                keep = (re.search(r"\b(?:keep|retain|preserve)(?:\s+(?:the|same)){0,2}\s*$", prefix)
                        and re.match(r"\s+(?:filter|restriction)\b", suffix)) or (
                        re.search(r"فیلتر\s*$", prefix) and re.match(r"\s+را\s+نگه دار", suffix))
                if keep and match.polarity == "positive":
                    retained_filters.append(condition)
    protected = (*metrics.spans, *dimensions.spans, *filters.spans)
    text = scoped.masked(protected)
    projection, grouping_requested = _total_projection(text, metrics, grouping, current_spec)
    operations, unresolved_operation = _operation_mentions(original, protected)
    found = [item for item in _MONTH_PATTERN.finditer(text)
             if item.group() != "may" or re.search(r"\b(?:in|during|for|month of)\s*$", text[:item.start()])
             or re.match(r"\s+[0-9]{4}(?![0-9])", text[item.end():]) or text == "may"]
    calendars = {_MONTHS[item.group()][0] for item in found}
    years = list(re.finditer(r"(?<![0-9])[0-9]{4}(?![0-9])", text))
    roles = _period_roles(text, found, years)
    grain, missing, clarification = None, None, None
    unresolved_details = []
    def need(slot, reason):
        unresolved_details.append((slot, reason))
        return slot, reason
    if current_spec is not None and any((current_spec.dataset_id, f.filter_id) in filters.negative for f in retained_filters):
        missing, clarification = need("filter_value", "filter_conflict")
    selected, forbidden, unresolved = [], [], unresolved_operation
    for kind, pattern in GRAIN_PHRASES:
        for match in re.finditer(r"(?<!\w)(?:" + pattern + r")(?!\w)", text):
            polarity = scoped.polarity(*match.span())
            if polarity in {"positive", "negative"}:
                (forbidden if polarity == "negative" else selected).append(kind)
            elif polarity == "unresolved":
                unresolved = True
    selected, forbidden = list(dict.fromkeys(selected)), tuple(dict.fromkeys(forbidden))
    # Removing the grouping property has the explicit alternative 'none'. A
    # bare exclusion does not choose one of the other available grains.
    off = (r"remove (?:the )?(?:(?:daily|weekly|monthly|time) )?grouping|"
           r"(?:no|without) (?:time|date) (?:grouping|breakdown)|"
           r"(?:روزانه|هفتگی|ماهانه|زمانی) را حذف کن|بدون تفکیک زمانی|کل (?:بازه|دوره)|"
           r"(?:whole|entire) period|period totals|ungrouped")
    if any(scoped.polarity(*match.span()) == "positive" for match in re.finditer(off, text)):
        selected.append("none")
    non_temporal = re.search(r"\b(?:group(?:ed)? by|by)\s+(?!(?:day|week|month|quarter|year|date|time)\b)\w+|"
                             r"به تفکیک\s+(?!(?:روز|هفته|ماه|فصل|سال|تاریخ|زمان)(?!\w))\w+", text)
    if forbidden and not selected and non_temporal:
        selected.append("none")
    date_groups = tuple((dataset.id, dimension.id) for dataset in catalog.datasets
                        if "day" in forbidden and dataset.time is not None
                        for dimension in dataset.dimensions if dimension.column == dataset.time.column)
    if set(selected).intersection(forbidden) or len(set(selected)) > 1:
        missing, clarification = need("grouping", "grain_conflict")
    elif forbidden and not selected:
        missing, clarification = need("grouping", "grain_replacement")
    if unresolved:
        missing, clarification = need("grouping", "quoted_requirement")
    if any(ref in dimensions.positive for ref in date_groups):
        missing, clarification = need("grouping", "grain_conflict")
    if metrics.ambiguous or set(metrics.positive).intersection(metrics.negative):
        missing, clarification = need("measure", "metric_ambiguity")
    if grouping.ambiguous or set(grouping.positive).intersection(dimensions.negative):
        missing, clarification = need("grouping", "dimension_ambiguity")
    if (current_spec is not None and metrics.negative and not metrics.positive
            and all((current_spec.dataset_id, key) in metrics.negative for key in current_spec.metric_ids)):
        missing, clarification = need("measure", "metric_replacement")
    if grounded.missing in {'multiple_ordering','filter_operator'}:
        operations = tuple(dict.fromkeys((*operations,'other')))
    elif grounded.missing:
        missing, clarification = need(grounded.missing, "control_ambiguity")
    if current_spec is not None and conflicting_filters(tuple(dict.fromkeys((
            *grounded.filters, *(FilterRequirement(current_spec.dataset_id,c) for c in retained_filters))))):
        missing, clarification = need('filter_value', 'filter_conflict')
    criterion = scoped.find(r"\bask\s+(?:me\s+)?for\s+(?:the\s+)?(?:metric|measure|criterion)\b|"
                            r"(?:معیار|شاخص)(?: را)? بپرس")
    if not metrics.positive and any(m.polarity == 'positive' for m in criterion):
        missing, clarification = need('measure', 'metric_criterion')
    for match in re.finditer(r"(?<!\w)(?:hourly|minutely|ساعتی|دقیقه ای)(?!\w)", text):
        if scoped.polarity(*match.span()) == "positive":
            operations = tuple(dict.fromkeys((*operations, "other")))
    if len(selected) == 1:
        grain = selected[0]
        # A "monthly comparison" and "values for each month" of a two-month
        # comparison do not request extra buckets inside either period.
        if (grain == "month" and _COMPARISON.search(text)
                and not re.search(r"در هر ماه|به تفکیک ماه|ماه به ماه|\bper month\b|\bmonth by month\b", text)):
            grain = None
        jalali = ("میلادی" not in text and "gregorian" not in text
                  and (calendars == {"jalali"} or "شمسی" in text or "jalali" in text
                       or (not calendars and catalog.preferred_calendar == "jalali")))
        if grain == "month" and jalali:
            grain = "jalali_month"
    result = RequestEvidence(time_grain=grain, operations=operations, metrics=metrics.positive,
                             projection=projection, grouping_requested=grouping_requested,
                             unresolved=tuple(dict.fromkeys(unresolved_details)),
                             dimension_choices=grouping.alternatives,
                             forbidden_grains=forbidden, excluded_metrics=metrics.negative,
                             excluded_dimensions=tuple(dict.fromkeys((*dimensions.negative, *date_groups))),
                             excluded_filters=tuple(dict.fromkeys((*filters.negative, *grounded.removed_filters))),
                             missing=missing, clarification=clarification, dimensions=grouping.positive,
                             retained_filters=tuple(dict.fromkeys(retained_filters)),
                             filter_requirements=grounded.filters, ordering=grounded.ordering,
                             pending_filter_value=grounded.pending_value, pending_filter=grounded.pending_filter)
    keep_filters = scoped.find(r"\b(?:keep|retain|preserve)\s+(?:(?:the|same|all)\s+)?filters\b|"
                               r"فیلتر(?:ها| ها)(?: را)? (?:حفظ کن|نگه دار)")
    if current_spec is not None and any(m.polarity == 'positive' for m in keep_filters):
        result = replace(result, filters_complete=True)
    if not found:
        numeric, missing = _numeric_period(text)
        result = replace(result, period=numeric)
        if numeric is None and missing is None and current_spec is not None:
            from sageql.sdk.grounding import refinement
            from sageql.sdk.periods import _has_date_evidence
            if refinement(original, current_spec) and not _has_date_evidence(text):
                result = replace(result, period=current_spec.period)
                removal = scoped.find(r"\b(?:remove|clear|drop)\s+(?:the\s+)?comparison\b|"
                                      r"مقایسه(?: را)? حذف|بدون مقایسه")
                keep = scoped.find(r"\b(?:keep|retain|preserve)\s+(?:(?:the|same)\s+)?comparison\b|"
                                   r"مقایسه(?: را)? (?:حفظ کن|نگه دار)")
                if any(m.polarity == 'positive' for m in removal):
                    result = replace(result, comparison=None, comparison_specified=True)
                elif (any(m.polarity == 'positive' for m in keep)
                      or not re.search(r"\b(?:comparison|compare|versus)\b|مقایسه", text)):
                    result = replace(result, comparison=current_spec.comparison, comparison_specified=True)
        return _period_missing(result, missing) if missing else result
    if len(calendars) != 1 and (grain is not None or not (_COMPARISON.search(text) or roles)):
        return _period_missing(result, "calendar")
    calendar = next(iter(calendars))
    # Named dates with day numbers are not whole-month evidence.
    if any(re.search(r"(?<![0-9])[0-9]{1,2}\s*$", text[:item.start()])
           or re.match(r"\s+[0-9]{1,2}(?![0-9])", text[item.end():]) for item in found):
        return result
    if not years:
        return _period_missing(result, "year")
    if len(calendars) > 1 and len(years) != len(found):
        return _period_missing(result, "year")
    selections, associated_years = [], set()
    for index, item in enumerate(found):
        if len(years) == 1:
            year = int(years[0].group())
        else:
            end = found[index + 1].start() if index + 1 < len(found) else len(text)
            adjacent_after = [value for value in years if item.end() <= value.start()
                              and not text[item.end():value.start()].strip()]
            adjacent_before = [value for value in years if value.end() <= item.start()
                               and not text[value.end():item.start()].strip()]
            local = (adjacent_after or adjacent_before
                     or [value for value in years if item.end() <= value.start() < end])
            if len(local) != 1:
                return _period_missing(result, "year") if roles else result
            associated_years.add(local[0].span())
            year = int(local[0].group())
        try:
            if _MONTHS[item.group()][0] == "jalali":
                jalali_month_bounds(year, _MONTHS[item.group()][1])
            else:
                date(year, _MONTHS[item.group()][1], 1)
        except ValueError:
            return _period_missing(result, "period")
        selections.append(PeriodSelection("jalali_month" if _MONTHS[item.group()][0] == "jalali" else "month",
                                          year=year, month=_MONTHS[item.group()][1]))
    if len(years) > 1 and associated_years != {year.span() for year in years}:
        # A bare year refinement can be combined with an earlier user month.
        # Do not anchor that old month while silently discarding the new year.
        return _period_missing(result, 'year') if roles else result
    if roles:
        if any(polarity != 'positive' for _, _, polarity in roles):
            return (_period_missing(result, 'period') if any(p in {'positive', 'unresolved'} for _, _, p in roles)
                    else result)
        selected_roles = {key: selections[index] for key, index, _ in roles}
        if (len(selected_roles) != len(roles)
                or {index for _, index, _ in roles} != set(range(len(selections)))):
            return _period_missing(result, 'period')
        if current_spec is not None:
            selected_roles.setdefault('period', current_spec.period)
            selected_roles.setdefault('comparison', current_spec.comparison)
        if 'period' not in selected_roles:
            return _period_missing(result, 'period')
        return replace(result, **selected_roles, comparison_specified=True)
    if len(selections) == 1:
        # One new named month after an explicit reference to the current
        # report is the comparison operand, not a replacement base period.
        # Negative, quoted and literal occurrences supply no such instruction.
        relative_comparison = scoped.find(
            r"\bcompare\s+(?:that|this|the same|the current|the previous)\s+(?:total|report|period)\s+with\b")
        if any(m.polarity == 'positive' and m.end <= found[0].start() for m in relative_comparison):
            if current_spec is None:
                return _period_missing(replace(result, period=None), 'period')
            return replace(result, period=current_spec.period, comparison=selections[0], comparison_specified=True)
        comparative = _COMPARISON.search(text) or re.search(
            r"مقایسه|نسبت|تغییر|افت|کاهش|افزایش|ماه قبل|\b(?:compare|change|growth|decline|previous|before|last)\b", text)
        return replace(result, period=selections[0], comparison_specified=not comparative)
    between = text[found[0].end():found[1].start()]
    if (len(selections) == 2 and not _COMPARISON.search(text)
            and re.search(r"(?<!\w)(?:تا|through|to)(?!\w)", between)):
        first, last = selections
        try:
            if calendar == "jalali":
                start, end = jalali_month_bounds(first.year, first.month)[0], jalali_month_bounds(last.year, last.month)[1]
            else:
                start = date(first.year, first.month, 1)
                end = date(last.year + (last.month == 12), last.month % 12 + 1, 1)
            if start >= end:
                return _period_missing(result, "period")
            if calendar == "jalali":
                last_bounds = jalali_month_bounds(last.year, last.month)
                return replace(result, period=PeriodSelection(
                    "jalali_range", f"{first.year:04d}-{first.month:02d}-01",
                    f"{last.year:04d}-{last.month:02d}-{(last_bounds[1] - last_bounds[0]).days:02d}"))
            return replace(result, period=PeriodSelection("range", start.isoformat(), end.isoformat()))
        except ValueError:
            return _period_missing(result, "period")
    if _COMPARISON.search(text):
        if len(selections) > 2:
            return replace(result, operations=(*operations, "multiple_periods"))
        return replace(result, period=selections[0], comparison=selections[1], comparison_specified=True)
    return result


_QUESTIONS = {
    'year': ('کدام سال برای دورهٔ درخواستی مد نظر است؟', 'Which year should the requested period use?'),
    'calendar': ('کدام تقویم مد نظر است؟', 'Which calendar should the requested period use?'),
    'period': ('لطفاً بازهٔ تاریخی درخواستی را مشخص کنید.', 'Please specify the requested date period.'),
    'dimension': ('کدام بعد ثبت‌شده برای تفکیک مد نظر است؟', 'Which registered dimension should group the report?'),
    "ordering": (
        "کدام معیار یا بعد ثبت‌شده و کدام جهت ترتیب را می‌خواهید؟",
        "Which registered measure or dimension and ordering direction should I use?",
    ),
    "filter": (
        "کدام فیلترها باید حفظ یا حذف شوند؟ لطفاً موارد متناقض را مشخص کنید.",
        "Which registered filters and exact values should I use, retain or remove? Please clarify the selections.",
    ),
    "measure": (
        "کدام معیار ثبت‌شده را می‌خواهید؟ لطفاً معیار مورد نظر و موارد حذفی را مشخص کنید.",
        "Which registered measure should I use? Please specify the measure and exclusions.",
    ),
    "grouping": (
        "گزارش با چه تفکیک زمانی باشد؟ یک تفکیک سازگار یا مجموع کل دوره را مشخص کنید.",
        "Which time grouping should I use? Please specify one compatible grouping or totals for the whole period.",
    ),
    "quoted_requirement": (
        "عبارت نقل‌شده یک درخواست گزارش است یا فقط نام یا مثال؟ لطفاً منظور را مشخص کنید.",
        "Is the quoted phrase a report requirement or only a name/example? Please clarify its role.",
    ),
}


def _tabular_period_default(evidence, messages, catalog, current_spec):
    """A fresh dated table adds neither time breakdown nor unrequested ranking."""
    if (current_spec is not None
            or evidence.period is not None and evidence.period.kind == 'all'):
        return evidence
    if evidence.period is None and not any(slot in {'year', 'calendar', 'period'} for slot, _ in _details(evidence)):
        return evidence
    # Use scoped user evidence, excluding literal predicate values and registered
    # labels. Assistant suggestions cannot supply a presentation requirement.
    original = _user_text(messages)
    grounded = controls(original, catalog, current_spec)
    protected = tuple(span for kind in ('metrics', 'dimensions', 'filters')
                      for span in concept_evidence(original, catalog, kind).spans)
    text = ScopedText(original).masked((*grounded.spans, *protected))
    scoped = ScopedText(text)
    if any(m.polarity == 'positive' for m in scoped.find(r'\b(?:table|tabulate)\b|(?<!\w)جدول(?!\w)')):
        changes = {}
        if (evidence.time_grain is None and not evidence.forbidden_grains
                and not any(slot == 'grouping' for slot, _ in _details(evidence))):
            changes['time_grain'] = 'none'
        owners = {owner for owner, _ in (*evidence.metrics, *evidence.dimensions)}
        ordering_cues = scoped.find(r'\b(?:sort\w*|order\w*|rank\w*|top|bottom|highest|lowest|'
                                   r'largest|smallest|most|least|best|worst)\b|'
                                   r'مرتب|رتبه|بیشترین|کمترین|بالاترین|پایین ترین|برترین')
        if (evidence.ordering is None and grounded.missing in {None, 'filter_value'} and len(owners) == 1
                and not any(m.polarity in {'positive', 'unresolved'} for m in ordering_cues)):
            changes['plain_table'] = True
            totals = scoped.find(r'\b(?:whole|entire)\s+period\b|کل\s+(?:بازه|دوره)')
            groups = scoped.find(r'\b(?:by|for each|group\w*|breakdown)\b|به تفکیک|بر اساس|براساس')
            if (evidence.period is not None and not grounded.missing
                    and evidence.metrics and not evidence.dimensions and not evidence.dimension_choices
                    and any(m.polarity == 'positive' for m in totals)
                    and not any(m.polarity in {'positive', 'unresolved'} for m in groups)):
                # A filter owner is not an output grouping. A fresh explicit
                # period total with no grouping request has no business groups.
                changes['excluded_dimensions'] = tuple(dict.fromkeys((
                    *evidence.excluded_dimensions,
                    *((d.id, dim.id) for d in catalog.datasets if d.id in owners for dim in d.dimensions))))
        return replace(evidence, **changes)
    return evidence


def request_evidence(messages: tuple[Message, ...], catalog: ReportingCatalog,
                     current_spec: ReportSpec | None = None) -> RequestEvidence:
    from sageql.sdk.phrases import clarification_choice, clarification_literal, new_report_requested, question_spans
    if messages and new_report_requested(messages[-1].content):
        value = _current_evidence((messages[-1],), catalog, None)
        return replace(_tabular_period_default(value, (messages[-1],), catalog, None), new_report=True)
    evidence = _current_evidence(messages, catalog, current_spec)
    previous = next((i for i in range(len(messages) - 2, -1, -1) if messages[i].role == "assistant"), None)
    year_question = previous is not None and bool(re.search(
        r"\b(?:which|what|specify|provide)\b.{0,30}\byear\b|(?:چه|کدام).{0,10}سال|سال.{0,15}(?:مشخص|چیست)",
        words(messages[previous].content)))
    if previous is None or (not year_question and messages[previous].content not in {q for pair in _QUESTIONS.values() for q in pair}):
        return _tabular_period_default(evidence, messages, catalog, current_spec)
    # Known question roles reconstruct user requirements, not assistant values.
    prior = request_evidence(messages[:previous], catalog, current_spec)
    scoped_answer = ScopedText(messages[-1].content)
    answer_text = scoped_answer.without(question_spans(scoped_answer))
    evidence = _current_evidence((Message('user', answer_text),), catalog, current_spec)
    year_candidates = {}
    scoped_answer = ScopedText(answer_text)
    for start, end in scoped_answer.clauses():
        value = clarification_literal(scoped_answer.surface(start, end))
        if value is not None and _YEAR_ANSWER.fullmatch(words(value)):
            year_candidates[words(value)] = value
    year_answer = next(iter(year_candidates.values())) if len(year_candidates) == 1 else None
    supplied_period = None
    # A semantic grouping question can be followed by the ordinary year
    # question. Bind a year-only answer to the most recent still-incomplete
    # user month, never to a suggested year or the business clock.
    if (any(slot == 'year' for slot, _ in _details(prior))
            and evidence.period is None and year_answer is not None):
        for user in reversed(messages[:previous]):
            if user.role != "user":
                continue
            original_text = ScopedText(user.content).without(controls(user.content, catalog, current_spec).spans)
            original = _current_evidence((Message('user', original_text),), catalog, current_spec)
            if any(slot == 'year' for slot, _ in _details(original)):
                supplied = _current_evidence((Message('user', original_text + ' ' + year_answer),), catalog, current_spec)
                if supplied.period is not None:
                    supplied_period = supplied
                    evidence = replace(evidence, period=supplied.period, comparison=supplied.comparison,
                                       comparison_specified=supplied.comparison_specified,
                                       missing=None if evidence.missing == "year" else evidence.missing)
                break
            if original.period is not None:
                break
    resolved_details = set()
    if prior.pending_filter_value is not None or prior.pending_filter is not None:
        owners = {owner for owner, _ in prior.metrics}
        permitted = replace(catalog, datasets=tuple(d for d in catalog.datasets if not owners or d.id in owners))
        answer = answer_text
        resolved = controls(answer, permitted, current_spec, prior.pending_filter_value, prior.pending_filter)
        evidence = _current_evidence((Message('user', ScopedText(answer).without(resolved.spans)),), catalog, current_spec)
        evidence = replace(evidence, filter_requirements=resolved.filters,
                           pending_filter_value=resolved.pending_value,
                           pending_filter=resolved.pending_filter,
                           missing=resolved.missing, clarification="control_ambiguity" if resolved.missing else None)
    elif messages[previous].content in _QUESTIONS['filter']:
        # Re-projecting an old ambiguous request after access changes can make
        # its value unique. That reinterpretation is not the user's answer to
        # the still-pending question; require a current affirmative selection.
        choice = clarification_choice(answer_text, catalog, 'filters', tuple({d for d,_ in prior.metrics}))
        matching = tuple(r for r in prior.filter_requirements
                         if (r.dataset_id, r.condition.filter_id) in choice.selected)
        if len(matching) == 1 and prior.missing is None:
            evidence = _current_evidence((Message('user', ScopedText(answer_text).without(choice.spans)),), catalog, current_spec)
            evidence = replace(evidence, filter_requirements=matching)
        elif not evidence.filter_requirements and not evidence.retained_filters and not evidence.excluded_filters:
            evidence = replace(evidence, missing='filter_value', clarification='control_ambiguity')
    if prior.missing == 'ordering':
        # Resolve a known local target question from user text, preserving the
        # earlier direction/limit. Assistant wording supplies no metric/value.
        metric_choice = clarification_choice(answer_text, catalog, 'metrics', tuple({d for d,_ in prior.metrics}))
        dimension_choice = clarification_choice(answer_text, catalog, 'dimensions', tuple({d for d,_ in prior.metrics}))
        choices = tuple(dict.fromkeys((*metric_choice.selected, *dimension_choice.selected)))
        choice = replace(metric_choice, selected=choices,
                         spans=tuple(dict.fromkeys((*metric_choice.spans, *dimension_choice.spans))))
        answer = answer_text
        answer_order = evidence.ordering
        if len(choice.selected) == 1:
            owner, identifier = choice.selected[0]
            dataset = next(d for d in catalog.datasets if d.id == owner)
            answer = next(c.label for c in (*dataset.metrics, *dataset.dimensions) if c.id == identifier)
            evidence = _current_evidence((Message('user', ScopedText(answer_text).without(choice.spans)),), catalog, current_spec)
        combined = _user_text(messages[:previous]) + '; sort by ' + answer
        resolved = controls(combined, catalog, current_spec)
        if len(choices) > 1:
            evidence = replace(evidence, missing='ordering', clarification='control_ambiguity')
        elif resolved.ordering is not None and resolved.missing is None:
            order = resolved.ordering
            if answer_order is not None and answer_order.limit is not None:
                order = replace(order, limit=answer_order.limit)
            evidence = replace(evidence, ordering=order, missing=None, clarification=None)
            resolved_details.add('ordering')
    if prior.missing == 'measure':
        choice = clarification_choice(answer_text, catalog, 'metrics')
        if choice.selected:
            residual = _current_evidence((Message('user', ScopedText(answer_text).without(choice.spans)),), catalog, current_spec)
            evidence = replace(residual, metrics=tuple(dict.fromkeys((*choice.selected, *residual.metrics))),
                               metric_selection_complete=True)
            if prior.clarification == 'metric_criterion' and prior.ordering is not None:
                owner, identifier = choice.selected[0]
                evidence = replace(evidence, ordering=replace(prior.ordering, dataset_id=owner, target=identifier))
            resolved_details.add('measure')
            prior = replace(prior, metrics=tuple(ref for ref in prior.metrics if ref not in prior.excluded_metrics),
                            missing=None, clarification=None)
    if prior.clarification == 'dimension_ambiguity':
        choice = clarification_choice(answer_text, catalog, 'dimensions')
        if choice.selected:
            residual = _current_evidence((Message('user', ScopedText(answer_text).without(choice.spans)),), catalog, current_spec)
            evidence = replace(residual, dimensions=choice.selected)
            resolved_details.add('grouping')
    role = prior.quoted_role
    if prior.clarification == "quoted_requirement":
        answer = ScopedText(answer_text)
        literal = answer.find(r"\b(?:only|just) (?:an? )?(?:example|name|title|literal)\b|فقط (?:یک )?(?:مثال|نام|عنوان)")
        actual = answer.find(r"\b(?:requested|actual|wanted) (?:operation|requirement|calculation)\b|عملیات (?:درخواستی|مورد نظر)")
        if not re.search(r"\bnot (?:only|just)\b", answer.text):
            role = ("literal" if any(m.polarity == "positive" for m in literal) else
                    "positive" if any(m.polarity == "positive" for m in actual) else None)
        original = ScopedText(_user_text(messages[:previous]))
        if role and len(original.quotes) == 1:
            a, b = original.quotes[0]
            content = "; Show " + original.text[a + 1:b - 1] + "; " if role == "positive" else " "
            resolved = original.text[:a] + content + original.text[b:]
            prior = _current_evidence((Message("user", resolved),), catalog, current_spec)
        else:
            role = None
    if supplied_period is not None and evidence.period is None:
        evidence = replace(evidence, period=supplied_period.period, comparison=supplied_period.comparison,
                           comparison_specified=supplied_period.comparison_specified)
    metrics = tuple(dict.fromkeys((*prior.metrics, *evidence.metrics)))
    excluded_metrics = tuple(ref for ref in (*prior.excluded_metrics, *evidence.excluded_metrics)
                             if ref not in evidence.metrics)
    metrics = tuple(ref for ref in metrics if ref not in excluded_metrics)
    replaced_filters = {(r.dataset_id, r.condition.filter_id) for r in evidence.filter_requirements} | set(evidence.excluded_filters)
    if evidence.period is not None:
        resolved_details.update(('year', 'calendar', 'period'))
    if evidence.filter_requirements and not evidence.pending_filter and not evidence.pending_filter_value and evidence.missing != 'filter_value':
        resolved_details.add('filter_value')
    if prior.filter_requirements and all((r.dataset_id, r.condition.filter_id) in evidence.excluded_filters
                                         for r in prior.filter_requirements):
        resolved_details.add('filter_value')
    remaining = tuple(detail for detail in _details(prior) if detail[0] not in resolved_details
                      and not (detail[0] == 'grouping' and detail[1] in {'grain_conflict', 'grain_replacement'}
                               and evidence.time_grain is not None))
    remaining = tuple(dict.fromkeys((*remaining, *_details(evidence))))
    # Keep the actual pending role until it is answered; date parsing does not
    # retag it as another slot. Newly explicit conflicts remain independent.
    primary = next((d for d in remaining if d[0] == evidence.missing), None)
    primary = primary or next((d for d in remaining if d[0] == prior.missing), None)
    primary = primary or (remaining[0] if remaining else None)
    missing, clarification = primary if primary else (None, None)
    projection = evidence.projection
    if projection is None and not evidence.grouping_requested:
        projection = prior.projection
    combined = replace(evidence,
        projection=projection,
        grouping_requested=evidence.grouping_requested or prior.grouping_requested,
        confirmed_clarification_answer=bool(resolved_details.intersection(slot for slot, _ in _details(prior))),
        clarified_table_defaults=(prior.clarified_table_defaults or (
            current_spec is None and prior.plain_table and 'filter_value' in resolved_details
            and any(slot == 'filter_value' for slot, _ in _details(prior)))),
        unresolved=remaining,
        dimension_choices=tuple(dict.fromkeys((*prior.dimension_choices, *evidence.dimension_choices))),
        new_report=evidence.new_report or prior.new_report,
        filters_complete=evidence.filters_complete or prior.filters_complete,
        metric_selection_complete=evidence.metric_selection_complete or prior.metric_selection_complete,
        plain_table=evidence.plain_table or prior.plain_table,
        period=evidence.period or prior.period,
        comparison=evidence.comparison if evidence.comparison_specified else prior.comparison,
        comparison_specified=evidence.comparison_specified or prior.comparison_specified,
        time_grain=evidence.time_grain if evidence.time_grain is not None else prior.time_grain,
        forbidden_grains=tuple(dict.fromkeys(kind for kind in (*prior.forbidden_grains, *evidence.forbidden_grains)
                                             if kind != evidence.time_grain)),
        metrics=metrics, excluded_metrics=tuple(dict.fromkeys(excluded_metrics)),
        filter_requirements=tuple(dict.fromkeys((
            *(r for r in prior.filter_requirements if (r.dataset_id, r.condition.filter_id) not in replaced_filters),
            *evidence.filter_requirements))),
        ordering=evidence.ordering or prior.ordering,
        pending_filter_value=evidence.pending_filter_value,
        pending_filter=evidence.pending_filter,
        dimensions=tuple(dict.fromkeys(ref for ref in (*prior.dimensions, *evidence.dimensions)
                                       if ref not in evidence.excluded_dimensions)),
        retained_filters=tuple(dict.fromkeys((*[condition for condition in prior.retained_filters
            if current_spec is not None and (current_spec.dataset_id, condition.filter_id) not in evidence.excluded_filters],
            *evidence.retained_filters))),
        operations=tuple(dict.fromkeys((*prior.operations, *evidence.operations))), quoted_role=role,
        excluded_dimensions=tuple(dict.fromkeys((*prior.excluded_dimensions, *evidence.excluded_dimensions))),
        excluded_filters=tuple(dict.fromkeys((*[ref for ref in prior.excluded_filters
            if current_spec is None or not any(ref == (current_spec.dataset_id, condition.filter_id)
                                              for condition in evidence.retained_filters)], *evidence.excluded_filters))),
        missing=missing, clarification=clarification)
    return _tabular_period_default(combined, messages, catalog, current_spec)


def anchor_intent(intent, evidence: RequestEvidence):
    changes = {}
    if evidence.confirmed_clarification_answer:
        changes['turn_kind'] = 'answer'
    from sageql.sdk.intent import ConceptRef
    datasets = {ref.dataset_id for ref in (*intent.metrics, *intent.dimensions)}
    if len(datasets) == 1:
        required = tuple(ConceptRef(dataset, metric) for dataset, metric in evidence.metrics if dataset in datasets)
        changes["metrics"] = tuple(dict.fromkeys((*intent.metrics, *required)))
        if evidence.metric_selection_complete:
            changes['metrics'] = required
        required_dimensions = tuple(ConceptRef(dataset, key) for dataset, key in evidence.dimensions if dataset in datasets)
        required_dimensions += tuple(ConceptRef(dataset, key) for options in evidence.dimension_choices
                                     for dataset, key in options if dataset in datasets)
        changes["dimensions"] = tuple(dict.fromkeys((*intent.dimensions, *required_dimensions)))
    changes["metrics"] = tuple(ref for ref in changes.get("metrics", intent.metrics)
                               if (ref.dataset_id, ref.concept_id) not in evidence.excluded_metrics)
    changes["dimensions"] = tuple(ref for ref in changes.get("dimensions", intent.dimensions)
                                  if (ref.dataset_id, ref.concept_id) not in evidence.excluded_dimensions)
    if evidence.projection is not None and datasets == {evidence.projection.dataset_id}:
        changes['dimensions'] = tuple(ConceptRef(evidence.projection.dataset_id, key)
                                      for key in evidence.projection.dimension_ids)
    if intent.filters is not None and len(datasets) == 1:
        dataset = next(iter(datasets))
        changes["filters"] = tuple(condition for condition in intent.filters
                                   if (dataset, condition.filter_id) not in evidence.excluded_filters)
    if evidence.retained_filters:
        changes["filters"] = tuple(dict.fromkeys((*changes.get("filters", intent.filters or ()), *evidence.retained_filters)))
    if evidence.filter_requirements and len(datasets) == 1:
        changes["missing"] = tuple(item for item in changes.get("missing", intent.missing) if item != "filter_value")
        selected = list(dict.fromkeys((*[r.condition for r in evidence.filter_requirements if r.dataset_id in datasets],
                                      *evidence.retained_filters)))
        identifiers = {c.filter_id for c in selected}
        changes["filters"] = tuple(c for c in changes.get("filters", intent.filters or ())
                                   if c.filter_id not in identifiers) + tuple(selected)
    if evidence.ordering is not None:
        order = evidence.ordering
        selected = {ref.concept_id for ref in (*intent.metrics, *intent.dimensions)}
        if "measure" in changes.get("missing", intent.missing) and order.target not in selected:
            # The measure is still to be asked. A default-metric target would
            # pre-empt the user's choice; keep only the requested direction.
            changes["descending"] = order.descending
        else:
            changes.update(order_by=order.target, ordering_specified=True, descending=order.descending)
        if order.limit is not None:
            changes['limit'] = order.limit
    if evidence.period is not None:
        changes["period"] = evidence.period
        changes["missing"] = tuple(item for item in intent.missing if item not in {"period", "calendar", "year"})
    if evidence.comparison_specified:
        changes.update(comparison=evidence.comparison, comparison_specified=True)
    if evidence.time_grain is not None:
        changes["time_grain"] = evidence.time_grain
    removed = {key for _, key in (*evidence.excluded_metrics, *evidence.excluded_dimensions)}
    if intent.order_by in removed or evidence.time_grain == "none" and intent.order_by == "time_bucket":
        changes.update(order_by=None, ordering_specified=True)
    if evidence.missing:
        changes.update(period=None, comparison=None, comparison_specified=False,
                       missing=tuple(dict.fromkeys((*intent.missing, evidence.missing))))
    return replace(intent, **changes)


def evidence_feedback(evidence: RequestEvidence, spec: ReportSpec, today: date,
                      catalog: ReportingCatalog | None = None) -> str | None:
    from sageql.sdk.semantics import resolve_period
    if evidence.missing:
        return "explicit_" + evidence.missing + "_required"
    if evidence.projection is not None and (
            spec.dataset_id != evidence.projection.dataset_id
            or set(spec.dimension_ids) != set(evidence.projection.dimension_ids)):
        return 'explicit_projection_mismatch'
    grain = "month" if spec.time_grain == "jalali_month" else spec.time_grain
    if grain in evidence.forbidden_grains:
        return "excluded_time_grain"
    if any((spec.dataset_id, key) in evidence.excluded_metrics for key in spec.metric_ids):
        return "excluded_metric"
    if any((spec.dataset_id, key) in evidence.excluded_dimensions for key in spec.dimension_ids):
        return "excluded_dimension"
    if any((spec.dataset_id, condition.filter_id) in evidence.excluded_filters for condition in spec.filters):
        return "excluded_filter"
    if any(condition not in spec.filters for condition in evidence.retained_filters):
        return "retained_filter_mismatch"
    from sageql.sdk.intent import _condition_keys
    dataset = next((d for d in catalog.datasets if d.id == spec.dataset_id), None) if catalog else None
    if evidence.new_report or evidence.filters_complete:
        required = tuple(dict.fromkeys((*(r.condition for r in evidence.filter_requirements
                                         if r.dataset_id == spec.dataset_id), *evidence.retained_filters)))
        if _condition_keys(required, dataset) != _condition_keys(spec.filters, dataset):
            return 'new_report_filter_mismatch' if evidence.new_report else 'retained_filter_mismatch'
    if evidence.new_report:
        if evidence.ordering is None and (spec.order_by is not None or spec.descending):
            return 'new_report_ordering_mismatch'
        if (evidence.ordering is None or evidence.ordering.limit is None) and spec.limit != 100:
            return 'new_report_limit_mismatch'
    if (evidence.clarified_table_defaults and evidence.plain_table
            and spec.chart == 'table' and evidence.ordering is None
            and (spec.order_by is not None or spec.descending)):
        return 'unrequested_table_ordering'
    groups = {}
    for required in evidence.filter_requirements:
        groups.setdefault((required.dataset_id,required.condition.filter_id),[]).append(required.condition)
    for (owner,identifier), conditions in groups.items():
        required = tuple(dict.fromkeys((*conditions, *(c for c in evidence.retained_filters if c.filter_id==identifier))))
        proposed = tuple(c for c in spec.filters if c.filter_id == identifier)
        if (owner != spec.dataset_id or _condition_keys(required, dataset) != _condition_keys(proposed, dataset)):
            return "explicit_filter_mismatch"
    if evidence.ordering is not None:
        order = evidence.ordering
        if (order.dataset_id != spec.dataset_id or order.target != spec.order_by
                or order.descending is not None and order.descending != spec.descending):
            return "explicit_ordering_mismatch"
        if order.limit is not None and order.limit != spec.limit:
            return "explicit_limit_mismatch"
    for selected, proposed, name in ((evidence.period, spec.period, "period"),
                                      (evidence.comparison, spec.comparison, "comparison")):
        if selected is not None:
            if proposed is None or resolve_period(selected, today) != resolve_period(proposed, today):
                return "explicit_" + name + "_mismatch"
    if evidence.time_grain is not None and spec.time_grain != evidence.time_grain:
        return "explicit_time_grain_mismatch"
    if evidence.comparison_specified and evidence.comparison is None and spec.comparison is not None:
        return "unrequested_comparison"
    if any(dataset != spec.dataset_id or metric not in spec.metric_ids for dataset, metric in evidence.metrics):
        return "explicit_metric_mismatch"
    if evidence.metric_selection_complete and set(spec.metric_ids) != {key for owner, key in evidence.metrics if owner == spec.dataset_id}:
        return 'explicit_metric_mismatch'
    if any(dataset != spec.dataset_id or key not in spec.dimension_ids for dataset, key in evidence.dimensions):
        return "explicit_dimension_mismatch"
    if any(not any(owner == spec.dataset_id and key in spec.dimension_ids for owner, key in options)
           for options in evidence.dimension_choices):
        return 'explicit_dimension_mismatch'
    return None


def canonical_fixed_periods(evidence: RequestEvidence, spec: ReportSpec, today: date, *,
                            messages=(), catalog=None, current_spec=None) -> ReportSpec:
    """Keep a user-selected fixed calendar operation when a range has equal bounds.

    No dates, filters or other selections change. Non-equivalent/malformed ranges
    remain subject to ordinary rejection; explicit user ranges stay ranges.
    """
    from sageql.sdk.semantics import resolve_period
    fixed = {'month', 'year', 'jalali_month', 'jalali_year'}
    historical = {}
    if messages and catalog is not None and current_spec is not None:
        from sageql.sdk.grounding import refinement
        from sageql.sdk.periods import _has_date_evidence
        latest = messages[-1].content
        visible = ScopedText(latest).masked(controls(latest, catalog, current_spec).spans)
        if refinement(latest, current_spec) and not _has_date_evidence(visible):
            # Frozen range context is an existing provider contract. Recover
            # only the most recent explicit user calendar selection, only when
            # its dates agree with that context. Assistant prose supplies none.
            for index in range(len(messages) - 2, -1, -1):
                if messages[index].role != 'user':
                    continue
                prior = request_evidence(tuple(messages[:index + 1]), catalog)
                if prior.period is None and prior.comparison is None:
                    prior_text = messages[index].content
                    prior_visible = ScopedText(prior_text).masked(controls(prior_text, catalog).spans)
                    if _has_date_evidence(prior_visible):
                        break  # A later relative/ambiguous date instruction wins.
                    continue
                for field in ('period', 'comparison'):
                    selected = getattr(prior, field)
                    current = getattr(current_spec, field)
                    if isinstance(selected, PeriodSelection) and selected.kind in fixed and current is not None:
                        try:
                            if resolve_period(selected, today) == resolve_period(current, today):
                                historical[field] = selected
                        except SDKError:
                            pass
                break
    changes = {}
    for field, selected in (('period', evidence.period), ('comparison', evidence.comparison)):
        supplied = getattr(spec, field)
        if isinstance(selected, PeriodSelection) and selected.kind == 'range':
            selected = historical.get(field, selected)
        if (not isinstance(selected, PeriodSelection) or not isinstance(supplied, PeriodSelection)
                or selected.kind not in fixed
                or supplied.kind != 'range'):
            continue
        try:
            equal = resolve_period(selected, today) == resolve_period(supplied, today)
        except SDKError:
            continue
        if equal:
            changes[field] = selected
    return replace(spec, **changes) if changes else spec


def final_evidence_check(messages: tuple[Message, ...], catalog: ReportingCatalog, spec: ReportSpec,
                         today: date, language: str, current_spec: ReportSpec | None = None) -> None:
    """Engine gate for every provider, before lookups or report execution."""
    evidence = request_evidence(messages, catalog, current_spec)
    if evidence.operations:
        raise SDKError("unsupported", unsupported_message(evidence.operations, language),
                       stage="semantic_validation", reason="requirements")
    mismatch = evidence_feedback(evidence, spec, today, catalog)
    if mismatch:
        raise SDKError("intent_mismatch", "The report contradicts explicit request evidence.",
                       stage="semantic_validation", reason="request_evidence")


def evidence_question(evidence: RequestEvidence, language: str, messages=()) -> Interpretation | None:
    if not evidence.clarification or evidence.clarification == 'period_detail':
        return None
    measure = evidence.missing == "measure"
    kind = (evidence.missing if evidence.missing in {'year', 'calendar', 'period'} else
            'dimension' if evidence.clarification == 'dimension_ambiguity' else
            "ordering" if evidence.missing == "ordering" else
            "quoted_requirement" if evidence.clarification == "quoted_requirement" else
            "filter" if evidence.missing == "filter_value" else "measure" if measure else "grouping")
    question = _QUESTIONS[kind][0 if language == "fa" else 1]
    previous = next((item.content for item in reversed(messages[:-1]) if item.role == "assistant"), None)
    return Interpretation("needs_clarification", question=question,
                          clarification_key="evidence_ordering" if kind == "ordering" else "evidence_filter" if kind == "filter" else "evidence_measure" if measure else "evidence_grouping",
                          continues_clarification=previous == question)
