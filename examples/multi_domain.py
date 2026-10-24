"""Two synthetic host integrations; installed SageQL, no network or credentials.

The provider is scripted for these smoke tests. Production hosts supply their
configured ReportProvider (for example OpenAIReportAgent) at the same boundary.
"""

from contextlib import closing
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from pathlib import Path
import sqlite3
from tempfile import TemporaryDirectory
from typing import Callable

from sageql import Column, Table
from sageql.sdk import (
    AccessScope, ActorContext, DatasetAccess, DatasetDefinition, DimensionDefinition,
    EntityLabelDimension, EntityLookupDefinition, FilterDefinition, FullNameFilterDefinition,
    Interpretation, LookupQualifier, MetricDefinition, PeriodSelection, RelatedDimension,
    RelatedFilter, RelationshipDefinition, ReportingCatalog, ReportSpec, RowPolicy,
    ReportPolicy, SDKError, SageQL, SQLiteAdapter, SQLiteSessionStore, TimeDefinition, UserFilter,
    register_relationships,
)


TODAY = date(2026, 10, 15)
ACTOR = ActorContext("demo-reader", attributes={"store": "north", "branch": "N"})


def retail_policy(actor):
    store = actor.attributes.get("store")
    if not store:
        raise SDKError("access_denied", "An authenticated store is required.")
    return AccessScope((
        DatasetAccess("sales", policies=(RowPolicy("shop_key", "eq", (store,)),
                                        RowPolicy("voided", "eq", (False,)))),
        DatasetAccess("products", policies=(RowPolicy("shop_key", "eq", (store,)),
                                           RowPolicy("sellable", "eq", (True,)))),
    ), version="store-access-v1")


def library_policy(actor):
    branch = actor.attributes.get("branch")
    if not branch:
        raise SDKError("access_denied", "An authenticated library branch is required.")
    return AccessScope((
        DatasetAccess("loans", policies=(RowPolicy("branch_code", "eq", (branch,)),
                                        RowPolicy("retracted", "eq", (False,)))),
        DatasetAccess("books", policies=(RowPolicy("branch_code", "eq", (branch,)),
                                        RowPolicy("restricted", "eq", (False,)))),
    ), version="branch-access-v1")


def retail_catalog():
    sales, products = Table("sale_lines"), Table("merchandise")
    catalog = ReportingCatalog((
        DatasetDefinition("sales", "Retail sales", sales,
            tuple(Column(sales.key, name, kind) for name, kind in (
                ("shop_key", "nvarchar(200)"), ("voided", "bit"), ("sku_code", "nvarchar(200)"),
                ("sold_on", "date"), ("net_amount", "decimal"), ("quantity", "int"))),
            metrics=(MetricDefinition("revenue", "Net sales", "sum", "net_amount", "USD",
                                      description="Net line amount after discounts; not profit."),
                     MetricDefinition("units", "Units sold", "sum", "quantity", "items")),
            dimensions=(DimensionDefinition("sku", "Stock code", "sku_code"),
                        EntityLabelDimension("product_name", "Product", "sku_code", "products",
                                             "product_key", "product_key_filter", ("title",))),
            filters=(FilterDefinition("sku_filter", "Stock code", "sku_code"),),
            time=TimeDefinition("sold_on"), default_metric_ids=("revenue",),
            description="One sale line. Broad sales reports use net sales, not units or profit."),
        DatasetDefinition("products", "Product catalogue", products,
            tuple(Column(products.key, name, kind) for name, kind in (
                ("shop_key", "nvarchar(200)"), ("sku_code", "nvarchar(200)"), ("sku_name", "nvarchar(200)"),
                ("department", "nvarchar(200)"), ("sellable", "bit"))), metrics=(),
            dimensions=(DimensionDefinition("store", "Store", "shop_key"),
                        DimensionDefinition("product_key", "Stock code", "sku_code"),
                        DimensionDefinition("title", "Product title", "sku_name"),
                        DimensionDefinition("department", "Department", "department")),
            filters=(FilterDefinition("product_key_filter", "Stock code", "sku_code"),
                     FilterDefinition("department_filter", "Department", "department"),
                     FullNameFilterDefinition("title_filter", "Product name", "sku_name",
                                              ("eq",), ("sku_name",)))),
    ), version="retail-v1", ambiguous_ranking_terms=("best",), lookups=(
        EntityLookupDefinition("named_product", "Product name", "sales", "sku_filter", "products",
                               "product_key", "title_filter",
                               (LookupQualifier("product_department", "Department", "department_filter"),)),
    ))
    return register_relationships(catalog, (RelationshipDefinition(
        "sale_product", "sales", "products", (("shop_key", "shop_key"), ("sku_code", "sku_code")),
        dimensions=(RelatedDimension("department", "Department", "department"),),
        filters=(RelatedFilter("department_filter", "Department", "department_filter"),),
    ),))


def library_catalog():
    loans, books = Table("circulation_events"), Table("holdings")
    catalog = ReportingCatalog((
        DatasetDefinition("loans", "Library circulation", loans,
            tuple(Column(loans.key, name, kind) for name, kind in (
                ("branch_code", "nvarchar(200)"), ("retracted", "bit"), ("book_ref", "int"),
                ("checked_out", "date"), ("loan_days", "int"), ("patron_ref", "nvarchar(200)"))),
            metrics=(MetricDefinition("borrowings", "Borrowings", "count_rows"),
                     MetricDefinition("mean_duration", "Mean loan duration", "average", "loan_days", "days",
                                      selection_terms=("mean loan duration", "average loan days")),
                     MetricDefinition("days_per_reader", "Loan days per reader", "sum_per_participant",
                                      "loan_days", "days", selection_terms=("per reader",),
                                      participant_column="patron_ref")),
            dimensions=(DimensionDefinition("accession", "Accession number", "book_ref"),
                        EntityLabelDimension("book_title", "Book", "book_ref", "books", "book_key",
                                             "book_key_filter", ("title",))),
            filters=(FilterDefinition("book_filter", "Accession number", "book_ref"),),
            time=TimeDefinition("checked_out"), default_metric_ids=("borrowings",),
            description="One checkout event. Circulation means number of borrowings, not holdings or revenue."),
        DatasetDefinition("books", "Library holdings", books,
            tuple(Column(books.key, name, kind) for name, kind in (
                ("branch_code", "nvarchar(200)"), ("accession_no", "int"), ("book_title", "nvarchar(200)"),
                ("shelf_name", "nvarchar(200)"), ("restricted", "bit"))), metrics=(),
            dimensions=(DimensionDefinition("branch", "Library branch", "branch_code"),
                        DimensionDefinition("book_key", "Accession number", "accession_no"),
                        DimensionDefinition("title", "Book title", "book_title"),
                        DimensionDefinition("shelf", "Shelf", "shelf_name")),
            filters=(FilterDefinition("book_key_filter", "Accession number", "accession_no"),
                     FilterDefinition("shelf_filter", "Shelf", "shelf_name"),
                     FullNameFilterDefinition("title_filter", "Book title", "book_title",
                                              ("eq",), ("book_title",)))),
    ), version="library-v1", ambiguous_ranking_terms=("best",), lookups=(
        EntityLookupDefinition("named_book", "Book title", "loans", "book_filter", "books", "book_key",
                               "title_filter", (LookupQualifier("book_shelf", "Shelf", "shelf_filter"),)),
    ))
    return register_relationships(catalog, (RelationshipDefinition(
        "loan_holding", "loans", "books", (("branch_code", "branch_code"), ("book_ref", "accession_no")),
        dimensions=(RelatedDimension("shelf", "Shelf", "shelf"),),
        filters=(RelatedFilter("shelf_filter", "Shelf", "shelf_filter"),),
    ),))


def create_retail_data(path):
    with closing(sqlite3.connect(path)) as connection, connection:
        connection.execute("CREATE TABLE sale_lines (shop_key TEXT, voided BIT, sku_code TEXT, sold_on DATE, net_amount DECIMAL, quantity INT)")
        connection.execute("CREATE TABLE merchandise (shop_key TEXT, sku_code TEXT, sku_name TEXT, department TEXT, sellable BIT)")
        connection.executemany("INSERT INTO merchandise VALUES (?, ?, ?, ?, ?)", [
            ("north", "B1", "Field guide", "Books", 1), ("north", "G2", "Seeds", "Garden", 1),
            ("south", "B1", "Private product", "Private department", 1),
            ("north", "X3", "Withdrawn product", "Hidden department", 0),
        ])
        connection.executemany("INSERT INTO sale_lines VALUES (?, ?, ?, ?, ?, ?)", [
            ("north", 0, "B1", "2026-09-01", 30, 2), ("north", 0, "B1", "2026-09-02", 40, 3),
            ("north", 0, "G2", "2026-09-02", 45, 9), ("north", 1, "B1", "2026-09-01", 900, 90),
            ("south", 0, "B1", "2026-09-01", 800, 80), ("north", 0, "B1", "2026-10-01", 700, 70),
        ])


def create_library_data(path):
    with closing(sqlite3.connect(path)) as connection, connection:
        connection.execute("CREATE TABLE circulation_events (branch_code TEXT, retracted BIT, book_ref INT, checked_out DATE, loan_days INT, patron_ref TEXT)")
        connection.execute("CREATE TABLE holdings (branch_code TEXT, accession_no INT, book_title TEXT, shelf_name TEXT, restricted BIT)")
        connection.executemany("INSERT INTO holdings VALUES (?, ?, ?, ?, ?)", [
            ("N", 4101, "A brief history", "History", 0), ("N", 4102, "The night sky", "Science", 0),
            ("S", 4102, "Private title", "Private shelf", 0), ("N", 4103, "Restricted title", "Secret shelf", 1),
        ])
        connection.executemany("INSERT INTO circulation_events VALUES (?, ?, ?, ?, ?, ?)", [
            ("N", 0, 4101, "2026-09-01", 14, "r1"), ("N", 0, 4102, "2026-09-01", 2, "r1"),
            ("N", 0, 4102, "2026-09-02", 6, "r2"), ("N", 0, 4102, "2026-09-03", 10, "r2"),
            ("N", 1, 4102, "2026-09-01", 900, "r3"), ("S", 0, 4102, "2026-09-01", 800, "r4"),
            ("N", 0, 4101, "2026-10-01", 700, "r5"), ("N", 0, 4103, "2026-09-01", 600, "r6"),
        ])


@dataclass(frozen=True)
class Scenario:
    name: str
    catalog: ReportingCatalog
    policy: ReportPolicy
    create_data: Callable[[Path], None]
    question: str
    initial: ReportSpec
    refinement: str
    refined: ReportSpec
    expected: tuple
    refined_expected: tuple


def scenarios():
    september = PeriodSelection("month", year=2026, month=9)
    retail = Scenario("retail", retail_catalog(), retail_policy, create_retail_data,
        "Net sales by department in September, as a bar chart",
        ReportSpec("sales", ("revenue",), ("department",), period=september,
                   chart="bar", order_by="revenue", descending=True),
        "Only Books; show daily net sales as a line chart",
        ReportSpec("sales", ("revenue",), filters=(UserFilter("department_filter", "eq", ("Books",)),),
                   period=september, time_grain="day", chart="line", order_by="time_bucket"),
        (("Books", Decimal("70")), ("Garden", Decimal("45"))),
        ((date(2026, 9, 1), Decimal("30")), (date(2026, 9, 2), Decimal("40"))))
    shelves = (UserFilter("shelf_filter", "in", ("History", "Science")),)
    library = Scenario("library", library_catalog(), library_policy, create_library_data,
        "Borrowings by History and Science shelves in September, as a table",
        ReportSpec("loans", ("borrowings",), ("shelf",), filters=shelves, period=september,
                   order_by="borrowings", descending=True),
        "Show mean loan duration per shelf instead, as a bar chart",
        ReportSpec("loans", ("mean_duration",), ("shelf",), filters=shelves, period=september,
                   chart="bar", order_by="mean_duration", descending=True),
        (("Science", 3), ("History", 1)), (("History", Decimal("14")), ("Science", Decimal("6"))))
    return retail, library


class ScriptedProvider:
    def __init__(self, scenario):
        self.scenario = scenario

    def interpret(self, messages, current_spec, catalog, today):
        if current_spec is not None:
            return Interpretation("ready", self.scenario.refined)
        if messages[-1].content != "2026":
            return Interpretation("needs_clarification", question="Which year should September cover?")
        return Interpretation("ready", self.scenario.initial)


def main():
    with TemporaryDirectory(prefix="sageql-domains-") as directory:
        for scenario in scenarios():
            path = Path(directory) / (scenario.name + ".sqlite")
            scenario.create_data(path)
            engine = SageQL(catalog=scenario.catalog, database=SQLiteAdapter(path), policy=scenario.policy,
                provider=ScriptedProvider(scenario), clock=lambda: TODAY, execution="validated", language="en",
                sessions=SQLiteSessionStore(Path(directory) / (scenario.name + "-sessions.sqlite")))
            session = engine.create_session(ACTOR)
            missing = engine.submit(session.session_id, scenario.question, ACTOR, "ask", 0)
            first = engine.submit(session.session_id, "2026", ACTOR, "year", missing.revision)
            second = engine.submit(session.session_id, scenario.refinement, ACTOR, "refine", first.revision)
            if (missing.status != "needs_clarification" or first.report is None or second.report is None
                    or first.report.rows != scenario.expected or second.report.rows != scenario.refined_expected):
                raise RuntimeError(scenario.name + " smoke test failed")
            print(scenario.name + ": clarification, authorized report and refinement passed")


if __name__ == "__main__":
    main()
