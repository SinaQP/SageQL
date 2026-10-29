"""Phase 05 reference additions; no SDK imports or output-derived expectations."""
from copy import deepcopy
from decimal import Decimal
from evaluations.reference import expected_report, facts


def reference(domain, spec, bounds):
    reference_spec = deepcopy(spec)
    for condition in reference_spec.get("filters", []):
        if condition["filter_id"] == "fee_filter":
            condition["values"] = [Decimal(str(value)) for value in condition["values"]]
        if condition['operator'] == 'neq':
            # Reference arithmetic only: independently select the remaining
            # authored source members, excluding SQL NULLs. Never used by SDK.
            field = condition['filter_id'].removesuffix('_filter')
            condition['values'] = list(dict.fromkeys(row[field] for row in facts(domain)
                if row[field] is not None and row[field] not in condition['values']))
            condition['operator'] = 'in'
    # All source arithmetic/group/order logic remains the independent oracle.
    return expected_report(domain, reference_spec, bounds)
