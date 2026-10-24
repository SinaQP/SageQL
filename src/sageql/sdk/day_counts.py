"""User evidence for the fixed count of matching daily entity groups."""

from dataclasses import replace
import re

from sageql.conversation import Message
from sageql.sdk.intent import ReportIntent
from sageql.sdk.models import ReportSpec


def validate_matching_day_result(prepared, result) -> None:
    """Check the additive adapter contract before names replace identity cells."""
    from datetime import date
    from sageql.sdk.models import SDKError
    from sageql.sdk.semantics import _value, column_type

    spec = prepared.spec
    if not spec.include_matching_day_count:
        return
    try:
        fields = {field.id: i for i, field in enumerate(result.fields)}
        identity_index = fields[spec.dimension_ids[0]]
        day_index = fields["time_bucket"]
        count_index = fields["matching_day_count"]
        if result.fields[count_index].type != "integer":
            raise ValueError
        definition = next(item for item in prepared.dataset.dimensions if item.id == spec.dimension_ids[0])
        family = column_type(next(column.data_type for column in prepared.dataset.columns
                                  if column.name == definition.column))
        periods = {"base": prepared.period, "comparison": prepared.comparison_period}
        seen, counts, sizes = set(), {}, {}
        for row in result.rows:
            period_label = row[fields["period_label"]] if spec.comparison else "base"
            period = periods.get(period_label)
            identity, day, count = row[identity_index], row[day_index], row[count_index]
            if identity is not None:
                _value(identity, family, "adapter_failed")
            if period is None or type(day) is not date or not period.start <= day < period.end:
                raise ValueError
            key = (period_label, identity)
            daily_key = (*key, day)
            if daily_key in seen:
                raise ValueError
            seen.add(daily_key)
            sizes[key] = sizes.get(key, 0) + 1
            if identity is None:
                if count is not None:
                    raise ValueError
            elif type(count) is not int or not 1 <= count <= (period.end - period.start).days:
                raise ValueError
            if key in counts and counts[key] != count:
                raise ValueError
            counts[key] = count
        if any(identity is not None and (counts[(label,identity)] < size or
               not result.truncated and counts[(label,identity)] != size)
               for (label,identity),size in sizes.items()):
            raise ValueError
    except (ValueError, TypeError, KeyError, AttributeError, SDKError):
        raise SDKError("adapter_failed", "Database adapter returned invalid matching-day counts.") from None


def matching_day_context(intent: ReportIntent, messages: tuple[Message, ...],
                         current_spec: ReportSpec | None) -> ReportIntent:
    users = [item.content for item in messages if item.role == "user"]
    evidence = users if intent.turn_kind == "answer" else users[-1:]
    selected = None
    for value in reversed(evidence):
        text = " ".join(value.casefold().replace("\u200c", " ").split())
        day_count = r"(?:تعداد|شمار)(?:\s+کل)?\s+روز(?:ها(?:ی)?)?|(?:number of|count of|count)\s+(?:matching |qualifying |such |these )?days"
        if re.search(r"(?:بدون|حذف).{0,35}(?:" + day_count + r")|(?:" + day_count
                     + r").{0,45}(?:حذف|نشان نده|نمایش نده)|"
                     r"\b(?:remove|without|no)\b.{0,25}(?:day count|number of.{0,20}days|count of.{0,20}days)", text):
            selected = False
            break
        if re.search(day_count, text):
            selected = True
            break
    if selected is None:
        selected = (current_spec.include_matching_day_count
                    if current_spec is not None and intent.turn_kind in {"refine", "answer"}
                    else False)
    changes = {"include_matching_day_count": selected}
    if selected:
        changes["time_grain"] = "day"
    elif intent.order_by == "matching_day_count":
        # Removing the computed display field also removes its unavailable order.
        changes.update(order_by=None, ordering_specified=True)
    return replace(intent, **changes)
