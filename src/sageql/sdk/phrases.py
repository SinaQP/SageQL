"""Bounded phrase scope shared by request evidence and host vocabulary guards.

This classifies occurrences, not arbitrary sentences. It knows clause boundaries,
explicit en/fa exclusion cues and the role of quoted text. Unknown quote roles
stay unresolved. No SQL, permissions, calendar arithmetic or domain terms live
here; callers match only registered concepts or their existing operation grammar.
"""

from dataclasses import dataclass
import re


_NORMALIZE = str.maketrans({**dict(zip("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789")),
                          "ي": "ی", "ك": "ک", "\u200c": " ", "’": "'"})


def literal_words(text: str) -> str:
    """Normalize language/spacing without changing literal letter case."""
    return " ".join(text.translate(_NORMALIZE).split())


def words(text: str) -> str:
    return literal_words(text).casefold()


_BREAK = re.compile(r"[;,،؛؟?]|!(?!=)|\.(?=\s|$)|\b(?:but|however)\b|(?<!\w)(?:اما|ولی|بلکه)(?!\w)|"
                    r"\band\s+(?=(?:show|include|calculate|use|apply|keep|retain|not|without|omit|exclude|remove)\b)")
_NEGATIVE = re.compile(r"\b(?:not(?!\s+(?:only|just)\b)|no|don't|do not|never|without|omit|omitting|exclude|excluding|remove|"
                       r"leave out|leaving out|skip|stop|instead of|rather than)\b|(?<!\w)(?:بدون|حذف|به جای|نه(?!\s+تنها)|نمی خواهم|نمی خوام|نمیخوام)(?!\w)")
_POST_NEGATIVE = re.compile(r"^\s*(?:را\s+)?(?:دیگر\s+)?(?:نباشد|نباشه|نمی خواهم|نمی خوام|نمیخوام|"
                            r"(?:نشان|نمایش)\s+نده|حذف(?:\s+کن|\s+شود)?)(?!\w)|"
                            r"^\s*را\s+(?:\w+\s+){0,8}(?:(?:نشان|نمایش)\s+نده|حذف کن)(?!\w)|"
                            r"^\s*(?:anymore|is not wanted|should not be shown|must not be shown)\b")
_LITERAL = re.compile(r"\b(?:titles?|named|called|examples?|words?|phrases?|texts?|labels?|quotes?|terms?|says|said)\b|"
                      r"(?<!\w)(?:نام|عنوان|مثال|عبارت|متن|برچسب|نقل قول)(?!\w)")
_SELECTION = re.compile(r"\b(?:show|include|calculate|use|apply|follow|select|request|metric|measure|operation|grouping)"
                        r"(?:\s+(?:the|a|an|metric|measure|label|called|calculation|operation))*\s*$|"
                        r"(?:شاخص|معیار|محاسبه|نمایش|نشان بده|تفکیک)\s*$")
_QUOTES = re.compile(r'"[^"\n]*"|“[^”\n]*”|«[^»\n]*»|(?<!\w)\'[^\'\n]+\'(?!\w)')
_REPLACEMENT = re.compile(r"\b(?:replace|swap|exchange)\s+|"
                          r"\bchange\s+(?:the\s+)?(?:metric|measure|dimension|grouping)\s+from\s+")

GRAIN_PHRASES = (
    ("day", r"روزانه|هر روز|به تفکیک روز|daily|per day"),
    ("week", r"هفتگی|هر هفته|به تفکیک هفته|weekly|per week"),
    ("month", r"ماهانه|هر ماه|ماه به ماه|به تفکیک ماه|monthly|per month|month by month"),
    ("quarter", r"فصلی|هر فصل|quarterly|per quarter"),
    ("year", r"سالانه|هر سال|به تفکیک سال|yearly|annually|per year"),
)
_ADVERB = re.compile(r"(?<!\w)(?:" + "|".join(pattern for _, pattern in GRAIN_PHRASES) + r")(?!\w)")


@dataclass(frozen=True)
class Mention:
    start: int
    end: int
    polarity: str


class ScopedText:
    def __init__(self, text: str):
        self.source = text
        normalized, positions = [], []
        space = None
        # Keep an index into the original user text: business matching uses
        # normalized words, but a quoted SQL parameter retains exact spelling,
        # internal whitespace, Unicode and case.
        for index, char in enumerate(text):
            value = char.translate(_NORMALIZE).casefold()
            if value.isspace():
                if space is None:
                    space = index
                continue
            if space is not None and normalized:
                normalized.append(' ')
                positions.append(space)
            space = None
            normalized.extend(value)
            positions.extend([index] * len(value))
        self.text = ''.join(normalized)
        self._positions = positions
        self.quotes = tuple(match.span() for match in _QUOTES.finditer(self.text))
        self.breaks = tuple(match.span() for match in _BREAK.finditer(self.text)
                            if not any(a <= match.start() < b for a, b in self.quotes))

    def surface(self, start: int, end: int) -> str:
        """Recover literal case even when casefold expands a Unicode character."""
        return self.source[self._positions[start]:self._positions[end - 1] + 1] if start < end else ""

    def context(self, start: int, end: int) -> tuple[str, str]:
        left = max((stop for begin, stop in self.breaks if stop <= start), default=0)
        right = min((begin for begin, stop in self.breaks if begin >= end), default=len(self.text))
        return self.text[max(left, start - 120):start], self.text[end:min(right, end + 80)]

    def clauses(self) -> tuple[tuple[int, int], ...]:
        starts = (0, *(end for _, end in self.breaks))
        ends = (*(start for start, _ in self.breaks), len(self.text))
        return tuple(zip(starts, ends))

    def polarity(self, start: int, end: int) -> str:
        prefix, suffix = self.context(start, end)
        negative = bool(_NEGATIVE.search(prefix) or _POST_NEGATIVE.search(suffix.lstrip('"”»\'')))
        # Replacement selects its new concept and excludes the old one.
        replacement = _REPLACEMENT.search(prefix)
        if replacement:
            connector = re.search(r"\b(?:with|for|to)\b", prefix[replacement.end():])
            after = prefix[replacement.end() + connector.end():] if connector else ""
            negative = (not connector or bool(_NEGATIVE.search(after))
                        or bool(_POST_NEGATIVE.search(suffix.lstrip(chr(34) + "”»'"))))
        # In 'monthly, not daily sales', the excluded adverb finishes the
        # negative modifier; it does not exclude the following metric. A list
        # connector ('not daily or weekly') keeps the negative scope open.
        cues = tuple(_NEGATIVE.finditer(prefix))
        adverbs = tuple(_ADVERB.finditer(prefix, cues[-1].end())) if cues else ()
        if adverbs and not re.match(r"\s*(?:and|or|و|یا)(?!\w)", prefix[adverbs[-1].end():]):
            negative = bool(_POST_NEGATIVE.search(suffix.lstrip('"”»\'')))
        quoted = next(((a, b) for a, b in self.quotes if a < end and start < b), None)
        if quoted:
            a, b = quoted
            before, after = self.context(a, b)
            # A phrase used as a title/name/example is data, including when the
            # quoted phrase contains command verbs or negative words itself.
            selection = _SELECTION.search(before)
            post_selection = re.match(r"\s*(?:را\s+)?(?:\w+\s+){0,8}(?:نشان بده|نمایش بده|محاسبه کن)(?!\w)", after)
            literal = _LITERAL.search(before[-70:]) or re.match(
                r"\s*(?:was|were|is|are)\s+(?:(?:only|just)\s+)?(?:an?\s+)?(?:examples?|names?|labels?|terms?)\b", after)
            if literal and not (selection and re.search(r"\b(?:metric|measure)\b|شاخص|معیار", selection.group())):
                return "literal"
            if not selection and not post_selection and not negative:
                return "unresolved"
        if negative:
            return "negative"
        return "positive"

    def find(self, pattern: str) -> tuple[Mention, ...]:
        return tuple(Mention(match.start(), match.end(), self.polarity(*match.span()))
                     for match in re.finditer(pattern, self.text))

    def literal(self, value: str) -> tuple[Mention, ...]:
        return self.find(r"(?<!\w)" + re.escape(words(value)) + r"(?!\w)")

    def masked(self, spans: tuple[tuple[int, int], ...] = ()) -> str:
        """Mask data quotations/registered names while retaining text offsets."""
        ranges = (*spans, *((a, b) for a, b in self.quotes if self.polarity(a + 1, b - 1) == "literal"))
        result = list(self.text)
        for a, b in ranges:
            result[a:b] = " " * (b - a)
        return "".join(result)

    def without(self, spans: tuple[tuple[int, int], ...]) -> str:
        """Suppress parsed answer roles without normalizing unrelated literals."""
        result = list(self.source)
        for start, end in spans:
            if start < end:
                a, b = self._positions[start], self._positions[end - 1] + 1
                result[a:b] = ' ' * (b - a)
        return ''.join(result)


def new_report_requested(text: str) -> bool:
    scoped = ScopedText(text)
    for match in scoped.find(r'\b(?:start (?:a )?new report|new report|start over)\b|گزارش جدید'):
        prefix, suffix = scoped.context(match.start, match.end)
        if (match.polarity == 'positive' and not suffix.lstrip().startswith(('?', '؟'))
                and re.fullmatch(r'\s*(?:(?:please|now|actually|instead|create|i want|لطفا|لطفاً|حالا|اکنون)\s+)?(?:a\s+|یک\s+)?', prefix)):
            return True
    return False


@dataclass(frozen=True)
class ClarificationChoice:
    selected: tuple[tuple[str, str], ...] = ()
    spans: tuple[tuple[int, int], ...] = ()


def question_spans(scoped: ScopedText) -> tuple[tuple[int, int], ...]:
    """Unconfirmed answer clauses; questions inside quoted values are data."""
    result = []
    for start, end in scoped.clauses():
        ending = end < len(scoped.text) and scoped.text[end] in '?؟'
        if ending or re.match(r'(?:is|are|should|could|would|can|which|what)\b|(?:آیا|کدام)(?!\w)',
                              scoped.text[start:end].strip()):
            result.append((start, end + int(ending)))
    return tuple(result)


def clarification_choice(text: str, catalog, attribute: str, owners=()) -> ClarificationChoice:
    """Interpret bounded affirmative/rejected choices in a known pending slot.

    No translations or business synonyms are inferred. Clauses outside the
    choice grammar remain ordinary instructions for the caller to validate.
    """
    scoped = ScopedText(text)
    noun = {'filters': r'filter|فیلتر', 'metrics': r'metric|measure|معیار|شاخص',
            'dimensions': r'dimension|grouping|بعد|تفکیک'}[attribute]
    affirmative = (r"(?:(?:i (?:mean|meant)|(?:please )?(?:use|choose|select)|my choice is|"
                   r"it is|it's|(?:the )?(?:" + noun + r") is|منظورم|منظور من|"
                   r"(?:از|همان)|(?:" + noun + r"))\s+)?(?:the\s+)?(?:(?:" + noun + r")\s+)?")
    rejected = r"(?:(?:not|no|not the|do not use|don't use|نه|نه فیلتر)\s+)"
    suffix = (r"(?:\s+(?:" + noun + r"))?(?:\s+(?:please|is what i mean|است|هست|باشه|"
              r"را می خواهم|را می خوام|را می گویم|را انتخاب کن|را استفاده کن|استفاده کن))?")
    terms = {}
    for dataset in catalog.datasets:
        if owners and dataset.id not in owners:
            continue
        for concept in getattr(dataset, attribute):
            for term in (concept.label, *getattr(concept, 'selection_terms', ())):
                terms.setdefault(words(term), set()).add((dataset.id, concept.id))
    positives, negatives, spans = [], [], []
    questions = question_spans(scoped)
    for start, end in scoped.clauses():
        if any(a <= start and end <= b for a, b in questions):
            continue
        for term, refs in sorted(terms.items(), key=lambda item: -len(item[0])):
            matches = tuple(m for m in scoped.literal(term) if start <= m.start and m.end <= end)
            for match in matches:
                prefix = scoped.text[start:match.start].strip()
                after = scoped.text[match.end:end].strip()
                quoted = any(a < match.end and match.start < b for a, b in scoped.quotes)
                # Bare quoted labels are not confirmations; a quoted value is
                # handled by the filter-value parser, never this choice helper.
                explicit = bool(prefix.strip(' "“«\'') and re.fullmatch(affirmative, prefix.strip(' "“«\'') + ' '))
                if quoted:
                    if not explicit or match.polarity == 'literal':
                        continue
                    prefix, after = prefix.rstrip(' "“«\''), after.lstrip('"”»\' ')
                negative = match.polarity == 'negative' and bool(re.fullmatch(rejected, prefix + ' '))
                positive = (match.polarity in {'positive', 'unresolved'}
                            and bool(re.fullmatch(affirmative, prefix + (' ' if prefix else ''))))
                if not (negative or positive) or not re.fullmatch(suffix, (' ' + after) if after else ''):
                    continue
                spans.append((start, end))
                (negatives if negative else positives).extend(sorted(refs))
                break
    positive, negative = set(positives), set(negatives)
    selected = tuple(sorted(positive)) if len(positive) == 1 and not positive.intersection(negative) else ()
    return ClarificationChoice(selected, tuple(dict.fromkeys(spans)))


def clarification_literal(text: str) -> str | None:
    """Remove only an affirmative answer wrapper; an entire quote is data."""
    scoped = ScopedText(text)
    if any(a == 0 and b == len(scoped.text) for a, b in scoped.quotes):
        return text
    if (re.match(r"(?:not|no|don't|do not|is|are|which|what|can|should)\b|(?:نه|آیا|کدام)(?!\w)", scoped.text)
            or '?' in scoped.text or '؟' in scoped.text):
        return None
    prefix = re.match(r"(?:(?:i (?:mean|meant)|(?:please )?(?:use|choose|select)|the value is|"
                      r"the year is|منظورم|منظور من|مقدار|سال)\s+)", scoped.text)
    if not prefix:
        return text
    end = len(scoped.text.rstrip(' .!'))
    copula = re.search(r'\s+(?:است|هست)$', scoped.text[:end])
    if copula:
        end = copula.start()
    body = scoped.surface(prefix.end(), end)
    if re.match(r"(?:not|no|don't|do not|is|are|which|what|can|should)\b|(?:نه|آیا|کدام)(?!\w)", words(body)):
        return None
    return body


@dataclass(frozen=True)
class ConceptEvidence:
    positive: tuple[tuple[str, str], ...] = ()
    negative: tuple[tuple[str, str], ...] = ()
    ambiguous: bool = False
    spans: tuple[tuple[int, int], ...] = ()
    alternatives: tuple[tuple[tuple[str, str], ...], ...] = ()


GENERIC_MEANS = {"average", "mean", "avg", "میانگین", "متوسط"}


def concept_evidence(text: str, catalog, attribute: str = "metrics") -> ConceptEvidence:
    """Longest registered phrase wins; tied distinct concepts remain ambiguous.

    Generic averaging words remain advisory extraction vocabulary, not an exact
    deterministic output requirement. Host-specific labels and aliases retain
    their meaning, independently of the aggregation's implementation.
    """
    scoped = ScopedText(text)
    terms = {}
    for dataset in catalog.datasets:
        for concept in getattr(dataset, attribute):
            aliases = getattr(concept, "selection_terms", ())
            for term in (concept.label, *(t for t in aliases if words(t) not in GENERIC_MEANS)):
                terms.setdefault(words(term), set()).add((dataset.id, concept.id))
    found = []
    for term, refs in terms.items():
        for match in scoped.literal(term):
            # Predicates constrain a metric; they don't request its output.
            prefix, suffix = scoped.context(match.start, match.end)
            filter_reference = bool(re.search(r"\b(?:filter|condition|predicate)(?:\s+(?:by|on|for|the))?\s*$|"
                                              r"(?:فیلتر|شرط)(?:\s+روی)?\s*$", prefix)
                                    or re.match(r"\s*(?:filter|condition|predicate)\b|\s*(?:فیلتر|شرط)(?!\w)", suffix))
            if match.polarity == "negative" and ((attribute == "filters") != filter_reference):
                continue
            if match.polarity == 'negative' and attribute in {'metrics','dimensions'} and re.search(
                    r"\b(?:sort|order|rank)(?:ing)?\b|مرتب|ترتیب|رتبه بندی",prefix):
                # Rejecting a sort on a concept does not remove its report
                # column. The separate ordering contract owns that exclusion.
                continue
            if attribute == "metrics" and re.match(r"\s*(?:[<>=]|greater than|less than|بیشتر از|کمتر از)", suffix):
                continue
            found.append((match, refs))
    positive, negative, spans, ambiguous, furthest = [], [], [], False, -1
    for match, refs in sorted(found, key=lambda value: (value[0].start, -value[0].end)):
        if match.end <= furthest:
            continue
        furthest = match.end
        if match.polarity == "literal":
            continue
        if match.polarity == "negative":
            negative.extend(sorted(refs))
            spans.append((match.start, match.end))
            continue
        if match.polarity == "unresolved" or len(refs) != 1:
            ambiguous = True
            continue
        spans.append((match.start, match.end))
        (negative if match.polarity == "negative" else positive).extend(refs)
    return ConceptEvidence(tuple(dict.fromkeys(positive)), tuple(dict.fromkeys(negative)),
                           ambiguous, tuple(spans))


def grouping_evidence(text: str, catalog, owners=()) -> ConceptEvidence:
    """Explicit grouping connectors over permitted labels, scoped to the fact.

    Predicates, titles and mere mentions are not positive output requirements.
    Related source labels do not create artificial cross-dataset collisions.
    """
    scoped = ScopedText(text)
    occurrences = {}
    for dataset in catalog.datasets:
        if owners and dataset.id not in owners:
            continue
        for dimension in dataset.dimensions:
            for match in scoped.literal(dimension.label):
                prefix, suffix = scoped.context(match.start, match.end)
                connector = re.search(r"(?:\bby|\brank|\bfor each|به تفکیک|بر اساس|براساس)\s+(?:the\s+)?$", prefix)
                replacement = _REPLACEMENT.search(prefix)
                if replacement and re.search(r"\b(?:with|for|to)\s*$", prefix[replacement.end():]):
                    connector = True
                explicit = connector or re.match(r"\s+(?:grouping|groups|breakdown)(?!\w)", suffix)
                if explicit and match.polarity in {"positive", "unresolved"}:
                    occurrences.setdefault((match.start, match.end, match.polarity), set()).add((dataset.id, dimension.id))
    positive, alternatives, ambiguous = [], [], False
    furthest = -1
    for (start, end, polarity), refs in sorted(occurrences.items(), key=lambda item: (item[0][0], -item[0][1])):
        if end <= furthest:
            continue
        furthest = end
        if polarity == "unresolved":
            ambiguous = True
        elif len(refs) != 1:
            # Registered imports can expose the same business grouping in a
            # source and fact. Keep the requirement without choosing the fact.
            from sageql.sdk.models import RelatedAttributeDimension
            origins = set()
            for owner, identifier in refs:
                dataset = next(d for d in catalog.datasets if d.id == owner)
                dimension = next(d for d in dataset.dimensions if d.id == identifier)
                origins.add((dimension.source_dataset_id, dimension.source_dimension_id)
                            if isinstance(dimension, RelatedAttributeDimension) else (owner, identifier))
            if len(origins) == 1 and len({d for d, _ in refs}) == len(refs):
                alternatives.append(tuple(sorted(refs)))
            else:
                ambiguous = True
        else:
            positive.extend(refs)
    return ConceptEvidence(positive=tuple(dict.fromkeys(positive)), ambiguous=ambiguous,
                           alternatives=tuple(dict.fromkeys(alternatives)))
