"""Empty-only V2 importer. Does not call the destructive V1 initializer."""
import argparse
import os
from contextlib import contextmanager

from sqlalchemy import create_engine, func, inspect, select, text, MetaData
from sqlalchemy.engine import make_url

from backend.app.services.dataset_v2 import DEFAULT_OUTPUT, load_rows, validate

V2_DATABASE='erp_procurement_demo_v2'


def validate_target(url):
    try:
        parsed=make_url(url)
        if (parsed.drivername!='mysql+pymysql' or parsed.database!=V2_DATABASE
                or set(parsed.query)-{'charset'} or ('charset' in parsed.query and parsed.query['charset']!='utf8mb4')):
            raise ValueError()
    except Exception:
        raise ValueError('v2_target_required') from None
    return parsed


def verify_connected_target(connection):
    if connection.scalar(text('SELECT DATABASE()'))!=V2_DATABASE:
        raise ValueError('v2_target_required')


def verify_dataset_loaded(connection, dataset=DEFAULT_OUTPUT):
    """Compare imported reference data, not merely a hard-coded environment name."""
    validate(dataset)
    for table, expected in load_rows(dataset):
        fields=list(expected[0])
        actual=list(connection.execute(select(*(table.c[k] for k in fields))).tuples())
        if set(actual)!={tuple(row[k] for k in fields) for row in expected} or len(actual)!=len(expected):
            raise ValueError('v2_dataset_not_loaded:'+table.name)


def assert_empty(connection):
    meta=MetaData()
    meta.reflect(bind=connection)
    for name,table in meta.tables.items():
        if name=='alembic_version': continue
        if connection.scalar(select(func.count()).select_from(table)):
            raise ValueError('v2_database_nonempty')


def import_into_connection(connection, dataset=DEFAULT_OUTPUT, *, after_insert=None):
    if connection.dialect.name=='mysql':
        validate_target(connection.engine.url)
        verify_connected_target(connection)
    validate(dataset)
    assert_empty(connection)
    counts={}
    for table,rows in load_rows(dataset):
        connection.execute(table.insert(),rows)
        counts[table.name]=len(rows)
    if after_insert: after_insert()
    return counts


@contextmanager
def v2_environment(url):
    validate_target(url)
    previous=os.environ.get('DATABASE_URL')
    os.environ['DATABASE_URL']=make_url(url).render_as_string(hide_password=False)
    try: yield
    finally:
        if previous is None: os.environ.pop('DATABASE_URL',None)
        else: os.environ['DATABASE_URL']=previous


def import_v2(url, dataset=DEFAULT_OUTPUT, *, create_database=False):
    parsed=validate_target(url)
    validate(dataset)  # before touching any database
    if create_database:
        admin=create_engine(parsed.set(database=None),hide_parameters=True)
        try:
            with admin.connect() as c:
                c.execute(text('CREATE DATABASE IF NOT EXISTS erp_procurement_demo_v2 CHARACTER SET utf8mb4'))
        finally: admin.dispose()
    engine=create_engine(parsed,pool_pre_ping=True,hide_parameters=True)
    try:
        with engine.connect() as c:
            verify_connected_target(c)
            acquired=c.scalar(text("SELECT GET_LOCK('erp_procurement_demo_v2_import', 5)"))
            if acquired!=1: raise ValueError('v2_import_locked')
            c.commit()
            try:
                # Check BEFORE migrations as well as inside the data transaction.
                assert_empty(c)
                c.commit()
                from alembic import command
                from alembic.config import Config
                from backend.app.services.dataset_v2 import ROOT
                with v2_environment(url):
                    command.upgrade(Config(str(ROOT/'alembic.ini')),'head')
                with c.begin():
                    counts=import_into_connection(c,dataset)
                    verify_dataset_loaded(c,dataset)
                return {'database':V2_DATABASE,'version':validate(dataset)['version'],'counts':counts}
            finally:
                if c.in_transaction(): c.rollback()
                c.execute(text("SELECT RELEASE_LOCK('erp_procurement_demo_v2_import')"))
                c.commit()
    finally: engine.dispose()


def main():
    parser=argparse.ArgumentParser(description='Import only into empty erp_procurement_demo_v2; no overwrite/reset option.')
    parser.add_argument('--dataset',default=str(DEFAULT_OUTPUT))
    parser.add_argument('--create-database',action='store_true')
    args=parser.parse_args()
    # Explicit variable only: no fallback to DATABASE_URL/current .env target.
    url=os.environ.get('V2_DATABASE_URL')
    if not url: raise SystemExit('V2_DATABASE_URL_required')
    try:
        import json
        print(json.dumps(import_v2(url,args.dataset,create_database=args.create_database),ensure_ascii=False))
    except Exception as exc:
        # DBAPI/Alembic errors can include credentials; never stringify them.
        known=str(exc) if isinstance(exc,ValueError) and str(exc).startswith(('v2_','v1_')) else type(exc).__name__
        raise SystemExit('V2_import_failed:'+known) from None


if __name__=='__main__': main()
