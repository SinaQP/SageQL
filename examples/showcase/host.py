"""Synthetic host for the showcase site: a two-store bookshop and café chain.

Everything here is invented data. The host registers what may be reported on
and who may see what; the model only ever sees these registered labels.
"""

from contextlib import closing
from datetime import date, timedelta
import sqlite3

from sageql import Column, Table
from sageql.sdk import (
    AccessScope, ActorContext, DatasetAccess, DatasetDefinition, DimensionDefinition,
    EntityLabelDimension, EntityLookupDefinition, FilterDefinition, FullNameFilterDefinition,
    LookupQualifier, MetricDefinition, RelatedDimension, RelatedFilter, RelationshipDefinition,
    ReportingCatalog, RowPolicy, SDKError, TimeDefinition, register_relationships,
)

TODAY = date(2026, 10, 15)
# The host's authentication layer supplies this; the model never sees it.
ACTOR = ActorContext("manager-north", attributes={"store": "north"})

PRODUCTS = (
    ("B01", "The Little Prince", "Books", 12.0), ("B02", "One Hundred Years of Solitude", "Books", 18.0),
    ("B03", "The Blind Owl", "Books", 15.0), ("B04", "A Brief History of Time", "Books", 20.0),
    ("C01", "Espresso", "Café", 3.0), ("C02", "Saffron latte", "Café", 4.5),
    ("C03", "Date cake", "Café", 5.0),
    ("S01", "Notebook", "Stationery", 6.0), ("S02", "Fountain pen", "Stationery", 25.0),
    ("S03", "Desk calendar", "Stationery", 9.0),
)

LABELS = {
    "en": {
        "sales": "Sales", "products": "Product catalogue", "revenue": "Net sales",
        "units": "Units sold", "orders": "Sale lines", "sku": "Product code", "product": "Product",
        "store": "Store", "product_key": "Product code", "title": "Product title",
        "department": "Department", "named_product": "Product name",
        "sales_description": "One sale line. Net sales are after discounts; there is no cost or profit data.",
    },
    "fa": {
        "sales": "فروش", "products": "فهرست کالاها", "revenue": "فروش خالص",
        "units": "تعداد فروخته‌شده", "orders": "تعداد ردیف فروش", "sku": "کد کالا", "product": "کالا",
        "store": "فروشگاه", "product_key": "کد کالا", "title": "نام کالا",
        "department": "دپارتمان", "named_product": "نام کالا",
        "sales_description": "هر ردیف یک قلم فروش است. فروش خالص پس از تخفیف است؛ داده بهای تمام‌شده یا سود وجود ندارد.",
    },
}


# Physical names and policy values that must never reach the model. The builder
# checks every recorded model input against this list.
HIDDEN_FROM_MODEL = ("sale_lines", "products.listed", "net_amount", "store_code", "sold_on", "voided",
                     "quantity", "manager-north")
POLICY_COLUMNS = ("store_code", "voided", "listed")


def policy(actor):
    """Every query is bound to the caller's store; voided and hidden rows never count."""
    store = actor.attributes.get("store")
    if not store:
        raise SDKError("access_denied", "An authenticated store is required.")
    return AccessScope((
        DatasetAccess("sales", policies=(RowPolicy("store_code", "eq", (store,)),
                                        RowPolicy("voided", "eq", (False,)))),
        DatasetAccess("products", policies=(RowPolicy("store_code", "eq", (store,)),
                                           RowPolicy("listed", "eq", (True,)))),
    ), version="store-access-v1")


def catalog(language="en"):
    text = LABELS[language]
    sales, products = Table("sale_lines"), Table("products")
    result = ReportingCatalog((
        DatasetDefinition("sales", text["sales"], sales,
            tuple(Column(sales.key, name, kind) for name, kind in (
                ("store_code", "nvarchar(20)"), ("voided", "bit"), ("sku", "nvarchar(20)"),
                ("sold_on", "date"), ("net_amount", "decimal"), ("quantity", "int"))),
            metrics=(MetricDefinition("revenue", text["revenue"], "sum", "net_amount", "USD"),
                     MetricDefinition("units", text["units"], "sum", "quantity"),
                     MetricDefinition("orders", text["orders"], "count_rows")),
            dimensions=(DimensionDefinition("sku", text["sku"], "sku"),
                        EntityLabelDimension("product", text["product"], "sku", "products",
                                             "product_key", "product_key_filter", ("title",))),
            filters=(FilterDefinition("sku_filter", text["sku"], "sku"),),
            time=TimeDefinition("sold_on"), default_metric_ids=("revenue",),
            description=text["sales_description"]),
        DatasetDefinition("products", text["products"], products,
            tuple(Column(products.key, name, kind) for name, kind in (
                ("store_code", "nvarchar(20)"), ("sku", "nvarchar(20)"), ("title", "nvarchar(200)"),
                ("department", "nvarchar(50)"), ("listed", "bit"))), metrics=(),
            dimensions=(DimensionDefinition("store", text["store"], "store_code"),
                        DimensionDefinition("product_key", text["product_key"], "sku"),
                        DimensionDefinition("title", text["title"], "title"),
                        DimensionDefinition("department", text["department"], "department")),
            filters=(FilterDefinition("product_key_filter", text["product_key"], "sku"),
                     FilterDefinition("department_filter", text["department"], "department"),
                     FullNameFilterDefinition("title_filter", text["named_product"], "title",
                                              ("eq",), ("title",)))),
    ), version="showcase-v1", preferred_calendar="jalali" if language == "fa" else "gregorian",
        lookups=(EntityLookupDefinition(
            "named_product", text["named_product"], "sales", "sku_filter", "products", "product_key",
            "title_filter", (LookupQualifier("product_department", text["department"], "department_filter"),)),))
    return register_relationships(result, (RelationshipDefinition(
        "sale_product", "sales", "products", (("store_code", "store_code"), ("sku", "sku")),
        dimensions=(RelatedDimension("department", text["department"], "department"),),
        filters=(RelatedFilter("department_filter", text["department"], "department_filter"),),
    ),))


def create_data(path):
    """Deterministic invented sales for July 1 to October 14, 2026, in two stores."""
    with closing(sqlite3.connect(path)) as connection, connection:
        connection.execute("CREATE TABLE sale_lines (store_code TEXT, voided BIT, sku TEXT, sold_on DATE, "
                           "net_amount DECIMAL, quantity INT)")
        connection.execute("CREATE TABLE products (store_code TEXT, sku TEXT, title TEXT, department TEXT, listed BIT)")
        connection.executemany("INSERT INTO products VALUES (?, ?, ?, ?, ?)", [
            (store, sku, title, department, 1)
            for store in ("north", "south") for sku, title, department, _ in PRODUCTS
        ] + [("north", "X99", "Discontinued mug", "Café", 0)])
        rows = []
        day = date(2026, 7, 1)
        while day < TODAY:
            n = day.toordinal()
            for index, (sku, _, department, price) in enumerate(PRODUCTS):
                for store, scale in (("north", 1), ("south", 2)):
                    quantity = (n * (index + 3) + (7 if store == "south" else 0)) % (9 if department == "Café" else 4)
                    if department == "Books" and day.month == 9:
                        quantity += 1  # A back-to-school bump that the trend examples show.
                    if quantity:
                        # Prices are multiples of 0.5, so every amount and sum is exact.
                        discount = 0.5 if n % 5 == 0 else 0
                        rows.append((store, 0, sku, day.isoformat(), quantity * price * scale - discount, quantity))
            if n % 11 == 0:
                rows.append(("north", 1, "B01", day.isoformat(), 999.0, 50))  # voided: never counted
            day += timedelta(days=1)
        connection.executemany("INSERT INTO sale_lines VALUES (?, ?, ?, ?, ?, ?)", rows)
