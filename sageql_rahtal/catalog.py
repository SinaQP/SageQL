"""Approved Rahtal daily-performance metadata, derived from Django models."""

from sageql.schema import Column, Definition, Relation, SchemaCatalog, Table


def daily_performance_catalog(schema: str = "dbo") -> SchemaCatalog:
    activity = Table("functionality_activities", schema)
    user = Table("authentication_user", schema)
    person = Table("persons_person", schema)
    specs = {
        activity.key: {
            "id": "int", "user_id": "int", "date": "date", "start_time": "time",
            "end_time": "time", "time": "float", "title_id": "int",
            "customer_id": "int", "product_id": "int", "order_id": "int",
            "importance_id": "int", "urgency_id": "int", "summary": "text",
            "is_deleted": "bit",
        },
        user.key: {"id": "int", "is_active": "bit"},
        person.key: {
            "user_id": "int", "first_name": "nvarchar", "last_name": "nvarchar",
            "job_position": "nvarchar", "is_deleted": "bit",
        },
    }
    columns = tuple(Column(table, name, kind) for table, fields in specs.items()
                    for name, kind in fields.items())
    return SchemaCatalog(
        (activity, user, person), columns,
        (
            Relation("activity_user", activity.key, ("user_id",), user.key, ("id",)),
            Relation("person_user", person.key, ("user_id",), user.key, ("id",)),
        ),
        (
            Definition("daily performance", "Each activity row is one registered daily work item.", "Rahtal Activities model"),
            Definition("activity hours", "Sum functionality_activities.time for total work hours; time is duration in hours.", "Rahtal Activities model"),
            Definition("employee name", "Use persons_person.first_name and last_name through activity_user and person_user; profiles may be absent.", "Rahtal Person model"),
            Definition("deleted records", "Exclude activity rows with is_deleted=1 and joined profiles with is_deleted=1.", "Rahtal soft-delete rules"),
        ),
    )


def policy_columns(schema: str = "dbo") -> dict[str, str]:
    return {f"{schema}.functionality_activities": "is_deleted",
            f"{schema}.persons_person": "is_deleted"}
