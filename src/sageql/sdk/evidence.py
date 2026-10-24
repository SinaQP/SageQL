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
from sageql.sdk.models import Interpretation, PeriodSelection, ReportingCatalog, ReportSpec, SDKError


def words(text: str) -> str:
    return " ".join(text.translate(str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789"))
                    .casefold().replace("ي", "ی").replace("ك", "ک").replace("\u200c", " ").split())


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


def operation_evidence(text: str) -> tuple[str, ...]:
    """Detect explicit unsupported operation families, never business entities."""
    text = words(text)
    # Explicit removal must not resurrect an unavailable part of an earlier
    # request. Keep other clauses so removing shares cannot hide an absence query.
    text = re.sub(r"(?:\b(?:without|omit|exclude|remove|do not include)\b|بدون|حذف)\s+"
                  r"(?:the\s+)?(?:percentage shares?|shares?(?: of (?:the )?total)?|percentages?|سهم(?: آن ها)?(?: از کل)?|درصد سهم)", "", text)
    result = []
    if re.search(r"(?:سهم.{0,70}(?:از کل|کل ساعات|کل مجموع)|درصد سهم|"
                 r"\b(?:percentage|percent|proportion|share)s?\b.{0,55}\b(?:of (?:the )?(?:total|all)|of each|share)\b|"
                 r"\bshare(?:s)? (?:of|in)\b)", text):
        result.append("percentage_share")
    if re.search(r"هیچ.{0,65}(?:ثبت نکرد|نداشته|انجام نداده)|"
                 r"\b(?:without any|with no)\b.{0,50}\b(?:records?|events?|facts?|rows?|data)\b|"
                 r"\b(?:never|no)\b.{0,35}\brecorded\b", text):
        result.append("absence")
    # This guard recognizes temporal extrema, not ordinary metric ranking.
    if (re.search(r"کدام (?:ماه|روز|هفته).{0,80}(?:بیشترین|کمترین)|"
                  r"\bwhich (?:month|day|week)\b.{0,65}\b(?:highest|lowest|most|least)\b", text)
            and re.search(r"بیشترین|highest|most", text)
            and re.search(r"کمترین|lowest|least", text)):
        result.append("series_extrema")
    if re.search(r"\b(?:top|highest|largest|primary)\b.{0,35}\b(?:within|for|per) each\b|"
                 r"\bfor each\b.{0,75}\b(?:top|highest|primary)\b|"
                 r"برای هر\s+\w+.{0,45}(?:برترین|اولین|بالاترین)", text):
        result.append("partitioned_ranking")
    return tuple(result)


@dataclass(frozen=True)
class RequestEvidence:
    period: PeriodSelection | None = None
    comparison: PeriodSelection | None = None
    comparison_specified: bool = False
    time_grain: str | None = None
    missing: str | None = None
    operations: tuple[str, ...] = ()
    metrics: tuple[tuple[str, str], ...] = ()


def _metric_evidence(text: str, catalog: ReportingCatalog) -> tuple[tuple[str, str], ...]:
    """Exact, unambiguous host labels supplement fallible metric extraction.

    Longest overlapping labels win (e.g. average revenue vs revenue). Predicates
    and explicit removals are not output requirements. Synonyms still belong to
    semantic interpretation, not a core dictionary of business measures.
    """
    labels = {}
    for dataset in catalog.datasets:
        for metric in dataset.metrics:
            label = words(metric.label)
            if len(label) >= 4:
                labels.setdefault(label, set()).add((dataset.id, metric.id))
    matches = []
    for label, refs in labels.items():
        for found in re.finditer(r"(?<!\w)" + re.escape(label) + r"(?!\w)", text):
            prefix, suffix = text[max(0, found.start() - 25):found.start()], text[found.end():found.end() + 30]
            if (re.search(r"(?:without|remove|omit|exclude|بدون|حذف)\s*$", prefix)
                    or re.match(r"\s*(?:[<>=]|greater than|less than|بیشتر از|کمتر از|را حذف|را نشان نده)", suffix)):
                continue
            matches.append((found.start(), found.end(), refs))
    # A sweep avoids quadratic pairwise comparisons when user text repeats host
    # labels. Ambiguous longer labels still mask their contained shorter labels.
    selected, furthest = [], -1
    for start, end, refs in sorted(matches, key=lambda item: (item[0], -item[1])):
        if end <= furthest:
            continue
        furthest = end
        if len(refs) == 1:
            selected.append(next(iter(refs)))
    return tuple(dict.fromkeys(selected))


def _user_text(messages: tuple[Message, ...]) -> str:
    users = [item.content for item in messages if item.role == "user"]
    latest = words(users[-1]) if users else ""
    # A year-only clarification can complete the immediately preceding user's
    # named period. Never borrow a year from the assistant or business clock.
    if re.fullmatch(r"(?:سال\s+)?[0-9]{4}[.!؟?]?", latest) and len(users) > 1:
        return words(users[-2]) + " " + latest
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


def request_evidence(messages: tuple[Message, ...], catalog: ReportingCatalog) -> RequestEvidence:
    text = _user_text(messages)
    operations = operation_evidence(text)
    found = [item for item in _MONTH_PATTERN.finditer(text)
             if item.group() != "may" or re.search(r"\b(?:in|during|for|month of)\s*$", text[:item.start()])
             or re.match(r"\s+[0-9]{4}(?![0-9])", text[item.end():]) or text == "may"]
    calendars = {_MONTHS[item.group()][0] for item in found}
    grain = None
    grains = (("day", r"روزانه|هر روز|به تفکیک روز|\bdaily\b|\bper day\b"),
              ("week", r"هفتگی|هر هفته|به تفکیک هفته|\bweekly\b|\bper week\b"),
              ("month", r"ماهانه|هر ماه|ماه به ماه|به تفکیک ماه|\bmonthly\b|\bper month\b|\bmonth by month\b"),
              ("year", r"سالانه|هر سال|به تفکیک سال|\byearly\b|\bannually\b"))
    selected = [kind for kind, pattern in grains if re.search(pattern, text)]
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
    result = RequestEvidence(time_grain=grain, operations=operations, metrics=_metric_evidence(text, catalog))
    if not found:
        numeric, missing = _numeric_period(text)
        return replace(result, period=numeric, missing=missing)
    if len(calendars) != 1 and (grain is not None or not _COMPARISON.search(text)):
        return replace(result, missing="calendar")
    calendar = next(iter(calendars))
    # Named dates with day numbers are not whole-month evidence.
    if any(re.search(r"(?<![0-9])[0-9]{1,2}\s*$", text[:item.start()])
           or re.match(r"\s+[0-9]{1,2}(?![0-9])", text[item.end():]) for item in found):
        return result
    years = list(re.finditer(r"(?<![0-9])[0-9]{4}(?![0-9])", text))
    if not years:
        return replace(result, missing="year")
    if len(calendars) > 1 and len(years) != len(found):
        return replace(result, missing="year")
    selections = []
    for index, item in enumerate(found):
        if len(years) == 1:
            year = int(years[0].group())
        else:
            end = found[index + 1].start() if index + 1 < len(found) else len(text)
            local = [value for value in years if item.end() <= value.start() < end]
            if len(local) != 1:
                return result  # Ambiguous association remains with the interpreter.
            year = int(local[0].group())
        try:
            if _MONTHS[item.group()][0] == "jalali":
                jalali_month_bounds(year, _MONTHS[item.group()][1])
            else:
                date(year, _MONTHS[item.group()][1], 1)
        except ValueError:
            return replace(result, missing="period")
        selections.append(PeriodSelection("jalali_month" if _MONTHS[item.group()][0] == "jalali" else "month",
                                          year=year, month=_MONTHS[item.group()][1]))
    if len(selections) == 1:
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
                return replace(result, missing="period")
            if calendar == "jalali":
                last_bounds = jalali_month_bounds(last.year, last.month)
                return replace(result, period=PeriodSelection(
                    "jalali_range", f"{first.year:04d}-{first.month:02d}-01",
                    f"{last.year:04d}-{last.month:02d}-{(last_bounds[1] - last_bounds[0]).days:02d}"))
            return replace(result, period=PeriodSelection("range", start.isoformat(), end.isoformat()))
        except ValueError:
            return replace(result, missing="period")
    if _COMPARISON.search(text):
        if len(selections) > 2:
            return replace(result, operations=(*operations, "multiple_periods"))
        return replace(result, period=selections[0], comparison=selections[1], comparison_specified=True)
    return result


def anchor_intent(intent, evidence: RequestEvidence):
    changes = {}
    from sageql.sdk.intent import ConceptRef
    datasets = {ref.dataset_id for ref in (*intent.metrics, *intent.dimensions)}
    if len(datasets) == 1:
        required = tuple(ConceptRef(dataset, metric) for dataset, metric in evidence.metrics if dataset in datasets)
        changes["metrics"] = tuple(dict.fromkeys((*intent.metrics, *required)))
    if evidence.period is not None:
        changes["period"] = evidence.period
        changes["missing"] = tuple(item for item in intent.missing if item not in {"period", "calendar", "year"})
    if evidence.comparison_specified:
        changes.update(comparison=evidence.comparison, comparison_specified=True)
    if evidence.time_grain is not None:
        changes["time_grain"] = evidence.time_grain
    if evidence.missing:
        changes.update(period=None, comparison=None, comparison_specified=False,
                       missing=tuple(dict.fromkeys((*intent.missing, evidence.missing))))
    return replace(intent, **changes)


def evidence_feedback(evidence: RequestEvidence, spec: ReportSpec, today: date) -> str | None:
    from sageql.sdk.semantics import resolve_period
    if evidence.missing:
        return "explicit_" + evidence.missing + "_required"
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
    return None


def final_evidence_check(messages: tuple[Message, ...], catalog: ReportingCatalog, spec: ReportSpec,
                         today: date, language: str) -> None:
    """Engine gate for every provider, before lookups or report execution."""
    evidence = request_evidence(messages, catalog)
    if evidence.operations:
        raise SDKError("unsupported", unsupported_message(evidence.operations, language),
                       stage="semantic_validation", reason="requirements")
    mismatch = evidence_feedback(evidence, spec, today)
    if mismatch:
        raise SDKError("intent_mismatch", "The report contradicts explicit request evidence.",
                       stage="semantic_validation", reason="request_evidence")
