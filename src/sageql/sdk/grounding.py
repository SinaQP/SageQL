"""Local filter/order evidence over permitted business concepts, never row data.

The grammar is deliberately bounded. Filter values are free-form typed literals;
no vocabulary, query, model proposal or physical-name inference establishes their
owner. A value-only restriction needs a user-supplied concept or a unique matching
current typed condition. This module owns extraction; RequestEvidence owns the
effective constraints and both intent and final-spec enforcement.
"""
from dataclasses import dataclass, replace
from decimal import Decimal, InvalidOperation
import re

from sageql.sdk.models import DatasetDefinition, FilterDefinition, ReportingCatalog, ReportSpec, SDKError, UserFilter
from sageql.sdk.phrases import (ScopedText, clarification_choice, clarification_literal,
                               concept_evidence, grouping_evidence, new_report_requested, words)


@dataclass(frozen=True)
class FilterRequirement:
    """A permitted business owner and exact typed source-row predicate."""
    dataset_id: str
    condition: UserFilter


@dataclass(frozen=True)
class OrderingRequirement:
    """One business sort; null target clears, other null fields impose no value."""
    dataset_id: str
    target: str | None
    descending: bool | None = None
    limit: int | None = None


@dataclass(frozen=True)
class GroundedControls:
    filters: tuple[FilterRequirement, ...] = ()
    removed_filters: tuple[tuple[str, str], ...] = ()
    ordering: OrderingRequirement | None = None
    missing: str | None = None
    # User literal awaiting a filter identity; local only, never diagnostics.
    pending_value: tuple[str, str] | None = None
    pending_filter: tuple[str, str, str] | None = None
    spans: tuple[tuple[int, int], ...] = ()


_REFINE = (r"\b(?:keep|retain|preserve|same|previous|change|replace|reverse|remove|instead|now)\b|"
           r"نگه دار|حفظ|قبلی|همان|تغییر|جایگزین|معکوس|برعکس|حذف|به جای")
_REMOVE = r"\b(?:remove|clear|drop)\b|حذف"
_HIGH = r"\b(?:highest|largest|most|descending|desc)\b|بیشترین|بالاترین|نزولی"
_LOW = r"\b(?:lowest|smallest|least|ascending|asc)\b|کمترین|پایین ترین|صعودی"
_QUOTE = r'''"[^"\n]{1,1000}"|“[^”\n]{1,1000}”|«[^»\n]{1,1000}»|'[^'\n]{1,1000}' '''.strip()
_STOP = re.compile(r"\s+(?:in|during|by|sorted|ordered|sort|order|with|where|and|but|only)\b|"
                   r"\s+(?:در|به تفکیک|مرتب|فقط|را)(?!\w)|[,;؛،!؟?]|\.(?:\s|$)")


def refinement(text: str, current: ReportSpec | None) -> bool:
    scoped = ScopedText(text)
    visible = scoped.masked()
    return current is not None and not new_report_requested(text) and bool(
        re.search(_REFINE, visible))


def _literal(scoped: ScopedText, start: int) -> tuple[str | None, int]:
    """One quoted literal or a bounded unquoted phrase, with exact surface case."""
    start += len(scoped.text[start:]) - len(scoped.text[start:].lstrip())
    quoted = re.match(_QUOTE, scoped.text[start:])
    if quoted:
        end = start + quoted.end()
        return scoped.surface(start, end)[1:-1], end
    stop = _STOP.search(scoped.text, start)
    end = stop.start() if stop else len(scoped.text)
    value = scoped.surface(start, end).strip().rstrip('.')
    if not value or len(value) > 1000 or value[0] in '"“«\'' or re.search(r"[<>=]", value):
        return None, start
    return value, end


def _typed(value: str, dataset: DatasetDefinition, definition: FilterDefinition, operator: str) -> UserFilter:
    from sageql.sdk.semantics import _predicate, column_type
    from sageql.sdk.vocabulary import mapped_values
    column = next(c for c in dataset.columns if c.name == definition.column)
    mapped = mapped_values(definition, value)
    if len(mapped) > 1:
        raise ValueError
    if mapped:
        if operator not in definition.operators:
            raise ValueError
        _predicate(column, operator, (mapped[0],), 'invalid_spec')
        return UserFilter(definition.id, operator, (mapped[0],))
    family = column_type(column.data_type)
    if family == 'integer':
        value = words(value)
        if not re.fullmatch(r"[+-]?[0-9]+", value):
            raise ValueError
        value = int(value)
    elif family in {'decimal', 'number'}:
        value = Decimal(words(value))
    elif family == 'date':
        value = words(value)
    elif family == 'boolean':
        normalized = words(value)
        if normalized not in {'true','false','1','0','بله','خیر'}:
            raise ValueError
        value = normalized in {'true','1','بله'}
    if operator not in definition.operators:
        raise ValueError
    _predicate(column, operator, (value,), 'invalid_spec')
    return UserFilter(definition.id, operator, (value,))


def _list_literal(scoped: ScopedText, start: int) -> tuple[tuple[str, ...], int]:
    """Bounded parenthesized/bracketed IN members, excluding quoted separators."""
    while start < len(scoped.text) and scoped.text[start].isspace():
        start += 1
    if start == len(scoped.text) or scoped.text[start] not in '([':
        raise ValueError
    closing = ')' if scoped.text[start] == '(' else ']'
    quoted = scoped.quotes
    end = next((i for i in range(start + 1, min(len(scoped.text), start + 4002))
                if scoped.text[i] == closing and not any(a <= i < b for a,b in quoted)), None)
    if end is None:
        raise ValueError
    breaks = [start, *(i for i in range(start + 1, end) if scoped.text[i] == ','
                      and not any(a <= i < b for a,b in quoted)), end]
    values = []
    for a,b in zip(breaks,breaks[1:]):
        member = scoped.surface(a + 1,b).strip()
        parsed = ScopedText(member)
        value, stop = _literal(parsed,0)
        if value is None or stop != len(parsed.text):
            raise ValueError
        values.append(value)
    if not 1 <= len(values) <= 100:
        raise ValueError
    return tuple(values), end + 1


def conflicting_filters(requirements: tuple[FilterRequirement, ...]) -> bool:
    groups = {}
    for requirement in requirements:
        key = requirement.dataset_id, requirement.condition.filter_id
        groups.setdefault(key, set()).add(requirement.condition)
    for conditions in groups.values():
        operators = [condition.operator for condition in conditions]
        if len(set(operators)) != len(operators):
            return True  # Two different predicates for the same operator.
        selected = next((set(c.values) for c in conditions if c.operator == 'eq'), None)
        allowed = next((set(c.values) for c in conditions if c.operator == 'in'), None)
        excluded = {v for c in conditions if c.operator == 'neq' for v in c.values}
        if selected is not None and (selected <= excluded or allowed is not None and not selected <= allowed):
            return True
        if allowed is not None and allowed <= excluded:
            return True
    return False


def filter_controls(text: str, catalog: ReportingCatalog, current: ReportSpec | None = None,
                    pending_value: tuple[str, str] | None = None,
                    pending_filter: tuple[str, str, str] | None = None) -> GroundedControls:
    scoped = ScopedText(text)
    owners = {d for d, _ in concept_evidence(text, catalog).positive}
    if not owners and refinement(text, current):
        owners = {current.dataset_id}
    candidates = [d for d in catalog.datasets if not owners or d.id in owners]
    found, removed, spans, missing = [], [], [], None
    waiting = None
    unavailable = False
    if pending_value is not None:
        answer = clarification_choice(text, catalog, 'filters', tuple(d.id for d in candidates))
        answer_spans = answer.spans
        if not answer.selected:
            # A pending literal may be repeated with an affirmative owner:
            # "Use the Channel filter for Portal". Strip only the already
            # pending operand, then apply the same polarity/ambiguity grammar.
            # No owner is inferred from the value or from catalog tuple order.
            from sageql.sdk.phrases import question_spans
            suffixes, clauses = [], []
            questions = question_spans(scoped)
            for a, b in scoped.clauses():
                if any(x <= a and b <= y for x, y in questions):
                    continue
                for separator in re.finditer(r"\s+for\s+", scoped.text[a:b]):
                    start, operand = a + separator.start(), a + separator.end()
                    if any(x <= start < y for x, y in scoped.quotes):
                        continue
                    value, end = _literal(scoped, operand)
                    if (value is not None and words(value) == words(pending_value[0])
                            and not scoped.text[end:b].strip(' .!')):
                        suffixes.append((start, b)); clauses.append((a, b))
            if suffixes:
                answer = clarification_choice(scoped.without(tuple(suffixes)), catalog, 'filters',
                                              tuple(d.id for d in candidates))
                answer_spans = tuple(clauses) if answer.selected else ()
        spans.extend(answer_spans)
        if answer.selected:
            owner, identifier = answer.selected[0]
            dataset = next(d for d in candidates if d.id == owner)
            definition = next(f for f in dataset.filters if f.id == identifier)
            try:
                found.append(FilterRequirement(owner, _typed(pending_value[0], dataset, definition, pending_value[1])))
            except (ValueError, InvalidOperation, SDKError):
                missing = 'filter_value'
    if current and re.search(r"\b(?:remove|clear|drop) (?:all |the )?filters\b|"
                             r"فیلتر(?:ها| ها)?(?: و (?:مقایسه|مرتب سازی|ترتیب))*(?: را)? حذف", scoped.masked()):
        removed.extend((current.dataset_id,c.filter_id) for c in current.filters)
    occurrences = {}
    for dataset in candidates:
        for definition in dataset.filters:
            for match in scoped.literal(definition.label):
                if any(a <= match.start and match.end <= b for a, b in spans):
                    continue
                if match.polarity == 'literal':
                    continue
                prefix, suffix = scoped.context(match.start, match.end)
                keep = re.search(r"\b(?:keep|retain|preserve)(?: the)?\s*$",prefix) and re.match(r"\s+filter\b",suffix)
                if keep and current is None:
                    missing, waiting = 'filter_value', (dataset.id,definition.id,'eq')
                    continue
                removal = (re.search(_REMOVE, prefix) and (re.match(r"\s+filter\b", suffix) or
                           re.search(r"\bfilter\s*$",prefix))) or (
                    re.search(r"فیلتر\s*$", prefix) and re.match(r"\s+را\s+حذف", suffix))
                if removal:
                    removed.append((dataset.id, definition.id))
                    continue
                connector = re.match(r"\s*(?:filter\s*)?(?:(!=|<>|=)|\b(is not|is|equals|equal to|in)\b|برابر(?: با)?|مساوی(?: با)?)\s*", suffix)
                # Explicit predicate constructions; a grouping or bare label is
                # not a predicate. The value-only grammar below cannot guess it.
                bare = re.search(r"\b(?:for|filter(?:\s+(?:by|on|to))?|exclude|only)\s*$|(?:فقط|فیلتر)\s*$", prefix)
                if re.match(r"\s+را\s+نگه دار", suffix):
                    bare = None
                if connector and connector.group().strip() == 'in' and not bare and not re.match(r"\s+in\s*[([]", suffix):
                    connector = None
                replacement = re.search(r"\b(?:replace|change)\s*$", prefix) and re.match(r"\s+(?:with|to)\s+", suffix)
                if not connector and not bare and not replacement:
                    continue
                if replacement:
                    connector = re.match(r"\s+(?:with|to)\s+", suffix)
                start = match.end + (connector.end() if connector else 0)
                value, end = _literal(scoped, start)
                if (value is not None and re.search(r"\b(?:use|choose|select|change|replace)\s+(?:the\s+)?$", prefix)
                        and not any(a <= start < b for a, b in scoped.quotes)):
                    modifier = re.search(r"\s+instead$", scoped.text[start:end])
                    if modifier:
                        value = scoped.surface(start, start + modifier.start()).strip()
                if connector and connector.group().strip() == 'in':
                    try:
                        value, end = _list_literal(scoped,start)
                    except ValueError:
                        value = None
                if isinstance(value, str) and not any(a <= start < b for a, b in scoped.quotes):
                    # A terminal Persian copula is grammar only when the
                    # remaining full phrase is one registered alias. Exact
                    # full vocabulary terms and quoted/free-form values win.
                    from sageql.sdk.vocabulary import mapped_values
                    copula = re.search(r"\s+(?:باشد|باشه|است|هست)$", value)
                    canonical = any(isinstance(entry.value, str) and words(entry.value) == words(value)
                                    for entry in definition.value_vocabulary)
                    if copula and not canonical and not mapped_values(definition, value):
                        stem = value[:copula.start()]
                        if len(mapped_values(definition, stem)) == 1:
                            value = stem
                negative = (connector is not None and connector.group().strip() in {'!=','<>','is not'}) or (
                    match.polarity == 'negative' and not replacement)
                if negative and re.search(r"\b(?:do not|don't|never)\b",prefix):
                    value = None
                operator = 'neq' if negative else 'eq'
                if connector and connector.group().strip() == 'in':
                    operator = 'in'
                    if negative:
                        unavailable, value = True, None
                occurrences.setdefault((match.start, match.end), []).append((dataset, definition, value, operator, end))
    furthest = -1
    for (start, end), options in sorted(occurrences.items(), key=lambda item: (item[0][0], -item[0][1])):
        if end <= furthest:
            continue
        furthest = end
        spans.append((start, max(o[-1] for o in options)))
        if len(options) != 1:
            missing = 'filter_value'
            continue
        dataset, definition, value, operator, _ = options[0]
        if value is None:
            missing = 'filter_value'
            waiting = (dataset.id,definition.id,operator)
            continue
        try:
            if operator == 'in':
                typed = tuple(_typed(v,dataset,definition,operator).values[0] for v in value)
                condition = UserFilter(definition.id,operator,typed)
            else:
                condition = _typed(value, dataset, definition, operator)
        except (ValueError, InvalidOperation, SDKError):
            missing = 'filter_value'
            continue
        found.append(FilterRequirement(dataset.id, condition))
    if pending_filter is not None and not found and not removed:
        owner, identifier, operator = pending_filter
        dataset = next((d for d in candidates if d.id == owner),None)
        definition = next((f for f in dataset.filters if f.id == identifier),None) if dataset else None
        body = clarification_literal(text)
        value_text = ScopedText(body) if body is not None else ScopedText('')
        value, end = _literal(value_text,0)
        from sageql.sdk.vocabulary import mapped_values
        if (definition is not None and value is not None and not value_text.text[end:].strip(' .!?؟')
                and (len(value.split()) == 1 or value_text.quotes or mapped_values(definition,value))
                and not concept_evidence(body,catalog).positive):
            try:
                found.append(FilterRequirement(owner,_typed(value,dataset,definition,operator)))
                spans.append((0,len(scoped.text)))
            except (ValueError,InvalidOperation,SDKError):
                missing = 'filter_value'
        if not found:
            missing, waiting = 'filter_value', pending_filter
    # Explicit only-scope, with no named concept: never infer a business owner
    # from the word's plausibility or from a provider's proposed condition.
    # Registered terms establish ownership only inside a row-selection role.
    # Shared terms remain ambiguous; catalog tuple order grants no priority.
    concept_spans = concept_evidence(text, catalog).spans
    vocabulary = {}
    vocabulary_pending = None
    terms = {}
    for dataset in candidates:
        for definition in dataset.filters:
            for entry in definition.value_vocabulary:
                for term in entry.terms:
                    terms.setdefault(words(term), []).append((dataset,definition,entry.value))
    # One escaped literal matcher avoids compiling/scanning thousands of
    # independent expressions. The owner/value index is local to this call.
    pattern = r"(?<!\w)(?:" + '|'.join(re.escape(term) for term in sorted(terms,key=lambda term:(-len(term),term))) + r")(?!\w)"
    for match in scoped.find(pattern) if terms else ():
        if match.polarity == 'literal' or any(a <= match.start and match.end <= b for a,b in spans):
            continue
        prefix, suffix = scoped.context(match.start, match.end)
        prefix = prefix.rstrip(' "“«\'')
        role = re.search(r"\b(?:for|from|only|exclude|without|include only)\s*$|(?:برای|به جز|فقط)\s*$", prefix)
        if not role:
            continue
        operator = 'neq' if match.polarity == 'negative' else 'eq'
        quoted = next(((a,b) for a,b in scoped.quotes if a < match.start < b), None)
        partial = (quoted is not None and (match.start != quoted[0]+1 or match.end != quoted[1]-1)) or (
            quoted is None and bool(suffix.strip()) and not _STOP.match(scoped.text,match.end)
            and not re.match(r"[,;؛،.!؟?]",suffix.lstrip()))
        if partial:
            # A registered prefix is not authority for an entire unknown value.
            # Preserve that literal for an explicit owner answer instead.
            if quoted:
                literal,end = _literal(scoped,quoted[0])
            else:
                tail,end = _literal(scoped,match.end)
                literal = scoped.surface(match.start,max(end,match.end)).strip() if tail is not None else None
            missing, vocabulary_pending = 'filter_value', (literal,operator) if literal is not None else None
            spans.append((quoted[0] if quoted else match.start,max(end,match.end)))
            continue
        collision = any(a <= match.start and match.end <= b for a,b in concept_spans)
        vocabulary[match.start,match.end] = [(dataset,definition,value,operator,collision)
            for dataset,definition,value in terms[scoped.text[match.start:match.end]]]
    furthest = -1
    for (start,end), options in sorted(vocabulary.items(),key=lambda item:(item[0][0],-item[0][1])):
        if end <= furthest:
            continue
        furthest = end
        spans.append((start,end))
        choices = list(dict.fromkeys((d.id,f.id,value,op) for d,f,value,op,_ in options))
        if len(choices) != 1 or any(collision for *_,collision in options):
            missing, vocabulary_pending = 'filter_value', (scoped.surface(start,end),options[0][3])
            continue
        dataset, definition, value, operator, _ = options[0]
        if operator not in definition.operators:
            unavailable = True
            continue
        found.append(FilterRequirement(dataset.id,UserFilter(definition.id,operator,(value,))))
    protected = (*concept_spans, *spans)
    visible = scoped.masked(protected)
    pending = vocabulary_pending
    for pattern in (r"(?=\bfor\s+(.+?)\s+only\b)", r"\binclude only\s+(?:for\s+)?([^;؛،,.]+)", r"فقط برای\s+([^;؛،,.]+)"):
        for match in re.finditer(pattern, visible):
            a,b = match.span(1)
            if any(match.start() <= start < b for start, _ in scoped.breaks):
                continue
            if any(x <= match.start() < y for x,y in scoped.quotes):
                continue
            if not match.group(1).strip():
                continue
            if pattern.startswith(r"(?=") and any(not any(x <= nested.start() < y for x,y in scoped.quotes)
                    for nested in re.compile(r'\bfor\b').finditer(scoped.text, a, b)):
                continue
            # An outer report/date 'for' cannot swallow an already identified
            # metric, grouping or categorical operand. Lookahead permits the
            # inner genuine selector to be considered independently.
            if any(x < b and a < y for x,y in protected):
                continue
            # Stop an unquoted value before date/grouping prose.
            value, end = _literal(scoped, a)
            if pattern.startswith(r"(?="):
                value = scoped.surface(a,b).strip().strip('"“”«»\'')
            if not value:
                continue
            if not pattern.startswith(r"(?=") and len(value.split()) != 1 and not any(a <= match.start(1) < b for a,b in scoped.quotes):
                continue
            prior = [condition for condition in (current.filters if current else ())
                     if condition.operator in {'eq','neq'} and len(condition.values)==1 and str(condition.values[0])==value]
            if len(prior)==1 and refinement(text,current):
                found.append(FilterRequirement(current.dataset_id, prior[0]))
            else:
                pending, missing = (value,'eq'), 'filter_value'
            spans.append((match.start(), max(end,b)))
    if pending_value and not found and not removed:
        pending, missing = pending_value, 'filter_value'
    # Contradictory requirements never get resolved by tuple iteration order.
    if conflicting_filters(tuple(found)) or any((r.dataset_id,r.condition.filter_id) in removed for r in found):
        missing = 'filter_value'
    return GroundedControls(tuple(dict.fromkeys(found)),tuple(dict.fromkeys(removed)),
                            missing='filter_operator' if unavailable else missing,
                            pending_value=pending,pending_filter=waiting,spans=tuple(spans))


def ordering_controls(text: str, catalog: ReportingCatalog, current: ReportSpec | None = None
                      ) -> tuple[OrderingRequirement | None, str | None]:
    scoped = ScopedText(text)
    visible = scoped.masked()
    metrics = concept_evidence(text, catalog)
    owners = {d for d,_ in metrics.positive}
    if not owners and refinement(text,current):
        owners={current.dataset_id}
    refs=[]
    for dataset in catalog.datasets:
        if owners and dataset.id not in owners:
            continue
        for concept in (*dataset.metrics,*dataset.dimensions):
            for term in (concept.label,*getattr(concept,'selection_terms',()),*getattr(concept,'ranking_terms',())):
                for match in scoped.literal(term):
                    if match.polarity != 'literal':
                        refs.append((match.start,match.end,dataset.id,concept.id,concept in dataset.metrics))
    # Longest labels prevent contained aliases from supplying a second target.
    refs=[r for r in refs if not any(o[0]<=r[0] and r[1]<=o[1] and o[1]-o[0]>r[1]-r[0] for o in refs)]
    visible=scoped.masked(tuple((a,b) for a,b,*_ in refs))
    removal = re.search(r"(?:remove|clear|drop) (?:the )?(?:sort(?:ing)?|order(?:ing)?|rank(?:ing)?)\b|"
                        r"(?:ترتیب|رتبه بندی|مرتب سازی)(?: را)? حذف|حذف (?:ترتیب|رتبه بندی|مرتب سازی)",visible)
    reverse = re.search(r"\breverse (?:the )?(?:sort(?:ing)?|order(?:ing)?|rank(?:ing)?)\b|معکوس|برعکس",visible)
    keep = re.search(r"\b(?:keep|retain|preserve) (?:the )?(?:same )?(?:sort(?:ing)?|order(?:ing)?|rank(?:ing)?)\b|همان ترتیب",visible)
    directions=[]
    ranges=[]
    for pattern,direction in ((r"\bfrom (?:the )?(?:highest|largest|most) to (?:the )?(?:lowest|smallest|least)\b|از بیشترین به کمترین|از زیاد به کم",True),
                              (r"\bfrom (?:the )?(?:lowest|smallest|least) to (?:the )?(?:highest|largest|most)\b|از کمترین به بیشترین|از کم به زیاد",False)):
        ranges.extend((m.start(),m.end(),direction,scoped.polarity(*m.span())) for m in re.finditer(pattern,visible))
    for pattern,direction in ((_HIGH,True),(_LOW,False)):
        directions += [(m.start(),m.end(),direction,scoped.polarity(*m.span())) for m in re.finditer(pattern,visible)
                       if not re.search(r"\bat\s*$",visible[:m.start()])
                       and not any(a<=m.start() and m.end()<=b for a,b,_,_ in ranges)]
    directions.extend(ranges)
    numbers={'one':1,'two':2,'three':3,'four':4,'five':5,'six':6,'seven':7,'eight':8,'nine':9,'ten':10}
    ranked = re.search(r"\b(top|bottom)\s+([0-9]+|"+'|'.join(numbers)+r")\b",visible)
    limit=None
    if ranked and scoped.polarity(*ranked.span()) == 'positive':
        token = ranked.group(2)
        limit = int(token) if token.isdigit() else numbers[token]
        if not directions:
            directions.append((*ranked.span(),ranked.group(1)=='top','positive'))
    counted = re.search(r"\bshow (?:the )?([0-9]+|"+'|'.join(numbers)+r")\s+"
                        r"(?!(?:days?|weeks?|months?|years?)\b)(?:\w+\s+){1,5}(?:highest|lowest|most|least)\b|"
                        r"(?<!\w)([0-9]+)\s+(?!(?:روز|هفته|ماه|سال)(?!\w))\w+\s+(?:با\s+)?(?:بیشترین|کمترین)",visible)
    if counted and directions and scoped.polarity(*counted.span()) == 'positive':
        token = counted.group(1) or counted.group(2)
        limit = int(token) if token.isdigit() else numbers[token]
    if not (directions or removal or reverse or keep or re.search(r"\b(?:sort|order)\b|مرتب|ترتیب",visible)):
        return None,None
    if re.search(r"\b(?:then by|secondarily by|secondary sort)\b|سپس بر اساس",visible):
        return None,'multiple_ordering'
    owner=next(iter(owners)) if len(owners)==1 else current.dataset_id if current and refinement(text,current) else None
    defaults={(d.id,key) for d in catalog.datasets for key in d.default_metric_ids}
    if not defaults:
        all_metrics={(d.id,m.id) for d in catalog.datasets for m in d.metrics}
        if len(all_metrics)==1:
            defaults=all_metrics
    if owner is None and len({d for d,_ in defaults})==1:
        owner=next(iter(defaults))[0]
    from sageql.sdk.comparisons import decline_ranking_requested
    if decline_ranking_requested(scoped.text) and owner:
        return OrderingRequirement(owner,'absolute_decrease',True),None
    if removal:
        if directions or reverse or keep or owner is None:
            return None,'ordering'
        return OrderingRequirement(owner,None,None,100 if re.search(r"rank|رتبه",removal.group()) else None),None
    if reverse or keep:
        if current and not owners:
            owner=current.dataset_id
        if current is None or current.order_by is None or directions or owner != current.dataset_id:
            return None,'ordering'
        return OrderingRequirement(owner,current.order_by,not current.descending if reverse else current.descending,current.limit),None
    positive=[d for d in directions if d[3]=='positive']
    negative=[d for d in directions if d[3] in {'negative','unresolved'}]
    if len({d[2] for d in positive})>1 or (not positive and negative):
        return None,'ordering'
    # Prefer targets explicitly adjacent to a sort/direction cue. Otherwise a
    # unique requested measure can ground "highest amounts first".
    targets=set()
    for a,b,d,key,is_metric in refs:
        prefix,suffix=scoped.context(a,b)
        prefix, suffix = prefix.rstrip(' "“«\''), suffix.lstrip('"”»\'')
        direct=(re.search(r"(?:\b(?:sort|order|rank)(?:ed)?(?:\s+(?:by|on))?|بر اساس|براساس|به ترتیب)\s*$",prefix)
                or re.match(r"\s+order\b",suffix))
        adjacent=re.search(r"(?:"+_HIGH+'|'+_LOW+r")\s*$",prefix) or re.match(r"\s+(?:ascending|descending)\b",suffix)
        if not direct and positive and is_metric:
            # Host ranking aliases such as "hours" can occur after a fixed
            # noun phrase ("highest recorded hours"). The nearest concept in
            # that clause determines the target, not later requested measures.
            for start,end,_,_ in positive:
                candidates=[r for r in refs if r[4] and r[0]>=end and r[0]-end<=40
                            and not any(x>=end and y<=r[0] for x,y in scoped.breaks)]
                if candidates and a==min(r[0] for r in candidates):
                    adjacent=True
        if direct or adjacent:
            targets.add((d,key))
    if not targets and positive:
        targets=set(metrics.positive)
        if not targets and current and refinement(text,current):
            targets={(current.dataset_id,key) for key in current.metric_ids}
        if not targets and len(defaults)==1:
            targets=defaults
    if not targets and re.search(r"\bcalendar order\b|\boldest first\b|ترتیب زمانی",visible) and owner:
        targets={(owner,'time_bucket')}
        if not positive:
            positive=[(0,0,False,'positive')]
    if len(targets)!=1:
        return None,'ordering'
    dataset,target=next(iter(targets))
    direction=positive[0][2] if positive else None
    if negative and any(d[2]==direction for d in negative):
        return None,'ordering'
    return OrderingRequirement(dataset,target,direction,limit),None


def controls(text: str, catalog: ReportingCatalog, current: ReportSpec | None = None,
             pending_value: tuple[str, str] | None = None,
             pending_filter: tuple[str, str, str] | None = None) -> GroundedControls:
    filters=filter_controls(text,catalog,current,pending_value,pending_filter)
    masked=ScopedText(text).masked(filters.spans)
    ordering,missing=ordering_controls(masked,catalog,current)
    requirements=list(filters.filters)
    if refinement(text,current):
        changed={(r.dataset_id,r.condition.filter_id) for r in requirements}|set(filters.removed_filters)
        requirements=[FilterRequirement(current.dataset_id,c) for c in current.filters
                      if (current.dataset_id,c.filter_id) not in changed]+requirements
        if ordering is None and missing is None and current.order_by is not None:
            target=current.order_by
            selected=concept_evidence(masked,catalog)
            dimensions=concept_evidence(masked,catalog,'dimensions')
            groups=grouping_evidence(masked,catalog,(current.dataset_id,))
            removed = ((current.dataset_id,target) in dimensions.negative
                       or target=='time_bucket' and re.search(r"remove .*grouping",masked)
                       or target=='period_label' and re.search(r"remove comparison",masked)
                       or target in current.dimension_ids and groups.positive
                       and (current.dataset_id,target) not in groups.positive
                       or current.time_grain=='none' and current.dimension_ids
                       and all((current.dataset_id,key) in dimensions.negative for key in current.dimension_ids))
            if removed:
                target=None
            # A unique metric replacement carries its associated ordering.
            if (current.dataset_id,target) in selected.negative and len(selected.positive)==1:
                target=selected.positive[0][1]
            elif (target in current.metric_ids and len(selected.positive)==1
                  and selected.positive[0] != (current.dataset_id,target)
                  and not re.search(r"\b(?:add|also|include|keep)\b|همچنین|اضافه|نگه دار",masked)):
                target=selected.positive[0][1]
            if target is not None:
                ordering=OrderingRequirement(current.dataset_id,target,current.descending,current.limit)
    return replace(filters,filters=tuple(dict.fromkeys(requirements)),ordering=ordering,
                   missing=filters.missing or missing)
