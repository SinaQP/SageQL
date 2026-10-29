"""Two optional-vocabulary integrations; synthetic SQLite, no model/network."""
from contextlib import closing
from datetime import date
from decimal import Decimal
from pathlib import Path
import sqlite3
from tempfile import TemporaryDirectory
from types import SimpleNamespace

from sageql import Column, Table
from sageql.sdk import (AccessScope, ActorContext, DatasetAccess, DatasetDefinition,
    FilterDefinition, FilterValueDefinition, Interpretation, MetricDefinition,
    PeriodSelection, ReportingCatalog, ReportSpec, RowPolicy, SageQL, SQLiteAdapter,
    UserFilter)


def main():
    # The provider is deliberately scripted: the core independently checks the
    # alias against host registration. Live-model accuracy is not demonstrated.
    definitions = (
        ('retail', 'sale_lines', 'store', 'channel', 'net', 'channel_filter', 'Channel',
         'revenue', 'Net sales', 'USD', 'Web', ('Online', 'آنلاین'),
         [('north', 'Web', 120), ('north', 'Desk', 70), ('private', 'Web', 900)], Decimal(120)),
        ('library', 'loans', 'branch', 'shelf', 'duration', 'shelf_filter', 'Shelf',
         'loan_days', 'Loan days', 'days', 'Science', ('Scientific', 'علمی'),
         [('north', 'Science', 14), ('north', 'History', 8), ('north', 'Science', 6), ('private', 'Science', 800)], Decimal(20)),
    )
    with TemporaryDirectory(prefix='sageql-values-') as directory:
        for domain, table_name, scope_column, category, amount, filter_id, filter_label, metric, metric_label, unit, canonical, terms, rows, expected in definitions:
            table = Table(table_name)
            catalog = ReportingCatalog((DatasetDefinition(domain, domain.title(), table,
                (Column(table.key, scope_column, 'text'), Column(table.key, category, 'text'),
                 Column(table.key, amount, 'decimal')),
                metrics=(MetricDefinition(metric, metric_label, 'sum', amount, unit),),
                filters=(FilterDefinition(filter_id, filter_label, category,
                    value_vocabulary=(FilterValueDefinition(canonical, terms),)),)),))
            path = Path(directory) / (domain + '.sqlite')
            with closing(sqlite3.connect(path)) as connection, connection:
                # Fixture DDL is fixed host code in a disposable test database.
                connection.execute(f'CREATE TABLE "{table_name}" ("{scope_column}" TEXT, "{category}" TEXT, "{amount}" DECIMAL)')
                connection.executemany(f'INSERT INTO "{table_name}" VALUES (?, ?, ?)', rows)
            scope = AccessScope((DatasetAccess(domain, policies=(RowPolicy(scope_column, 'eq', ('north',)),)),))
            target = ReportSpec(domain, (metric,), period=PeriodSelection('all'),
                                filters=(UserFilter(filter_id, 'eq', (canonical,)),))
            provider = SimpleNamespace(interpret=lambda *args, selected=target: Interpretation('ready', selected))
            engine = SageQL(catalog=catalog, policy=lambda actor, current=scope: current,
                provider=provider, database=SQLiteAdapter(path), clock=lambda: date(2026,10,25),
                execution='validated', language='en')
            actor = ActorContext('synthetic-host-reader')
            session = engine.create_session(actor)
            reply = engine.submit(session.session_id, f'{metric_label} for {terms[0]} only.', actor, 'first', 0)
            if reply.status != 'report_ready' or reply.report.rows != ((expected,),):
                raise RuntimeError('Vocabulary example failed')
            print(f'{domain}: authorized alias report = {expected} {unit}')


if __name__ == '__main__':
    main()
