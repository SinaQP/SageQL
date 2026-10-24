"""Bounded evidence for common relative periods, without model date arithmetic."""

from dataclasses import replace
import re

from sageql.conversation import Message
from sageql.sdk.intent import ReportIntent
from sageql.sdk.models import PeriodSelection, ReportingCatalog, ReportSpec
from sageql.sdk.calendars import JALALI_MONTH_NAMES


_NUMBERS = {"یک": 1, "دو": 2, "سه": 3, "چهار": 4, "پنج": 5, "شش": 6,
            "هفت": 7, "هشت": 8, "نه": 9, "ده": 10, "یازده": 11, "دوازده": 12}
_UNITS = {"روز": "day", "هفته": "week", "ماه": "month", "فصل": "quarter", "سال": "year"}
_DIGITS = str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789")


def _has_date_evidence(text: str) -> bool:
    text = " ".join(text.translate(_DIGITS).casefold().replace("\u200c", " ").split())
    months = (*JALALI_MONTH_NAMES, "ژانویه", "فوریه", "مارس", "آوریل", "مه", "ژوئن", "ژوئیه", "اوت", "سپتامبر", "اکتبر", "نوامبر", "دسامبر",
              "january", "february", "march", "april", "may", "june", "july", "august", "september", "october", "november", "december")
    if any(re.search(r"(?<!\w)" + re.escape(name) + r"(?!\w)", text) for name in months):
        return True
    if re.search(r"(?<!\w)[0-9]{4}(?:[-/][0-9]{1,2})?(?!\w)", text):
        return True
    terms = ("امروز", "دیروز", "این هفته", "هفته قبل", "هفته گذشته", "این فصل", "فصل قبل",
             "همه تاریخ", "تمام تاریخ", "تمام سابقه", "all dates", "all data", "today", "yesterday")
    return (any(term in text for term in terms)
            or re.search(r"\b(?:last|this|past|recent|previous)\b.*\b(?:days?|weeks?|months?|quarters?|years?)\b", text) is not None)


def relative_period_evidence(text: str, preferred_calendar: str) -> PeriodSelection | None:
    """Recognize one explicit relative phrase; leave ambiguous/comparison text alone.

    These are typed period selections, not date conversions. No phrase grants
    access or supplies a year for an explicit month. Unrecognized wording still
    goes through ordinary intent extraction and semantic review.
    """
    text = " ".join(text.translate(_DIGITS).replace("ي", "ی").replace("ك", "ک").replace("\u200c", " ").split())
    persian = "شمسی" in text or "جلالی" in text
    gregorian = "میلادی" in text
    if persian and gregorian:
        return None
    calendar = "jalali" if persian else "gregorian" if gregorian else preferred_calendar
    matches = []
    count = r"(?:[0-9]{1,4}|" + "|".join(_NUMBERS) + r")"
    for found in re.finditer(r"(?<!\w)(" + count + r")\s+(روز|هفته|ماه|فصل|سال)(?:\s+(?:شمسی|میلادی))?\s+(?:گذشته|اخیر)(?!\w)", text):
        raw, unit = found.group(1, 2)
        selection = PeriodSelection("jalali_rolling" if calendar == "jalali" else "rolling",
                                    count=int(raw) if raw.isascii() and raw.isdigit() else _NUMBERS[raw], unit=_UNITS[unit])
        matches.append((found.span(), selection))
    patterns = (
        (r"(?:ماه\s+(?:قبل|گذشته|پیش)|(?:این\s+ماه|ماه\s+جاری))", "month"),
        (r"(?:سال\s+(?:قبل|گذشته|پیش)|پارسال|امسال|سال\s+جاری|این\s+سال)", "year"),
    )
    for pattern, unit in patterns:
        for found in re.finditer(r"(?<!\w)" + pattern + r"(?!\w)", text):
            if any(start <= found.start() < end for (start, end), _ in matches):
                continue
            current = found.group() in {"این ماه", "ماه جاری", "امسال", "سال جاری", "این سال"}
            kind = ("this_" if current else "last_") + ("jalali_" if calendar == "jalali" else "") + unit
            matches.append((found.span(), PeriodSelection(kind)))
    return matches[0][1] if len(matches) == 1 else None


def period_evidence_context(intent: ReportIntent, messages: tuple[Message, ...],
                            catalog: ReportingCatalog, current_spec: ReportSpec | None = None) -> ReportIntent:
    last = next((item.content for item in reversed(messages) if item.role == "user"), "")
    calendar_text = last.casefold()
    persian = any(term in calendar_text for term in ("شمسی", "جلالی", "jalali", "persian calendar"))
    gregorian = any(term in calendar_text for term in ("میلادی", "gregorian"))
    preserve_month = (intent.turn_kind in {"refine", "answer"} and current_spec is not None
                      and current_spec.time_grain == "month" and not persian)
    if (intent.time_grain == "month" and not gregorian and not preserve_month
            and (persian or catalog.preferred_calendar == "jalali")):
        intent = replace(intent, time_grain="jalali_month")
    selection = relative_period_evidence(last, catalog.preferred_calendar)
    if (current_spec is None and intent.turn_kind == "new" and selection is None
            and not _has_date_evidence(last)):
        from sageql.sdk.business import measure_question
        previous = next((item.content for item in reversed(messages[:-1]) if item.role == "assistant"), "")
        if previous in {measure_question(catalog, language).question for language in ("fa", "en")}:
            intent = replace(intent, turn_kind="answer")
    if (selection is not None and selection.kind in {"rolling", "jalali_rolling"}
            and intent.time_grain not in {None, "none"} and intent.turn_kind == "new"):
        normalized = " ".join(last.translate(_DIGITS).replace("\u200c", " ").split())
        count = r"(?:[0-9]{1,4}|" + "|".join(_NUMBERS) + r")"
        # Any explicitly counted non-temporal noun can be a row/group limit.
        # Entity vocabulary belongs to the host.
        temporal_units = r"روز|هفته|ماه|فصل|سال|days?|weeks?|months?|quarters?|years?"
        output_limit = re.search(r"(?<!\w)" + count + r"\s+(?!(?:" + temporal_units + r")(?!\w))\w+",
                                 normalized, re.I)
        limited_buckets = re.search(r"(?:آخرین|اولین|فقط|latest|first)\s+" + count + r"\s+(?:ماه|روز|هفته|months?|days?|weeks?)(?!\w)", normalized, re.I)
        if output_limit is None and limited_buckets is None and "limit" not in normalized.casefold():
            intent = replace(intent, limit=100)
    if selection is None and intent.turn_kind == "answer" and current_spec is None and not _has_date_evidence(last):
        for message in reversed(messages):
            if message.role == "user":
                selection = relative_period_evidence(message.content, catalog.preferred_calendar)
                if selection is not None:
                    break
    if (intent.turn_kind == "refine" and current_spec is not None
            and {ref.dataset_id for ref in (*intent.metrics, *intent.dimensions)} == {current_spec.dataset_id}
            and not {"period", "year", "calendar"}.intersection(intent.missing)):
        if selection is None and not _has_date_evidence(last):
            intent = replace(intent, period=current_spec.period)
    if intent.comparison is not None:
        return intent
    if (intent.turn_kind == "refine" and current_spec is not None
            and intent.period == current_spec.period):
        return intent  # Referring to the old report must not move its frozen dates.
    if selection is None:
        return intent
    return replace(intent, period=selection,
                   missing=tuple(item for item in intent.missing if item not in {"period", "calendar"}))
