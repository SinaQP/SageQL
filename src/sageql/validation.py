"""Conservative structural checks for proposed SQLite SQL."""

import sqlglot
from sqlglot import exp
from sqlglot.errors import ErrorLevel, ParseError

from sageql.errors import InvalidSQL


_READ_QUERY = (exp.Select, exp.Union, exp.Intersect, exp.Except)
_FORBIDDEN = (
    exp.Insert,
    exp.Update,
    exp.Delete,
    exp.Create,
    exp.Drop,
    exp.Alter,
    exp.Command,
    exp.Transaction,
    exp.Merge,
    exp.Into,
)


def validate_sql(sql: str) -> str:
    """Accept one parsed SQLite SELECT query; return its original SQL text.

    This is a structural filter for generated output, not permission to execute
    the SQL. Database permissions and read-only connections are still required.
    """
    if not isinstance(sql, str) or not sql.strip():
        raise InvalidSQL("model returned empty SQL")

    try:
        statements = sqlglot.parse(sql, read="sqlite", error_level=ErrorLevel.RAISE)
    except (ParseError, ValueError) as exc:
        raise InvalidSQL("model returned invalid SQLite SQL") from exc

    if len(statements) != 1 or statements[0] is None:
        raise InvalidSQL("expected exactly one SQL statement")

    statement = statements[0]
    if not isinstance(statement, _READ_QUERY):
        raise InvalidSQL("only SELECT queries are supported")
    if any(isinstance(node, _FORBIDDEN) for node in statement.walk()):
        raise InvalidSQL("query contains a disallowed SQL operation")

    return sql.strip()
