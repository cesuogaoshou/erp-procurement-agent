"""Real MySQL V2 only: empty guard and rollback, never falls back to V1."""
import hashlib
import json
import os
from decimal import Decimal

import pytest
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.exc import IntegrityError

from backend.app.db.import_v2_data import import_v2, validate_target, verify_dataset_loaded, verify_connected_target
from backend.app.models import Material, SupplierMaterial

pytestmark=pytest.mark.skipif(os.getenv('RUN_MYSQL_INTEGRATION')!='1',reason='opt-in V2 MySQL integration')


@pytest.fixture
def engine():
    url=os.environ.get('V2_DATABASE_URL')
    if not url: pytest.skip('explicit V2_DATABASE_URL required')
    validate_target(url)
    e=create_engine(url,hide_parameters=True)
    yield e
    e.dispose()


def fingerprint(engine):
    result={}
    with engine.connect() as c:
        for table in inspect(c).get_table_names():
            rows=sorted(json.dumps(dict(r._mapping),sort_keys=True,default=str) for r in c.execute(text('SELECT * FROM `'+table+'`')))
            result[table]=hashlib.sha256('\n'.join(rows).encode()).hexdigest()
    return result


def test_v2_mysql_import_nonempty_guard_preserves_every_table(engine):
    before=fingerprint(engine)
    with engine.connect() as c:
        verify_connected_target(c)
        verify_dataset_loaded(c)
    with pytest.raises(ValueError,match='v2_database_nonempty'):
        import_v2(os.environ['V2_DATABASE_URL'])
    assert fingerprint(engine)==before


def test_v2_mysql_fk_failure_rolls_back_whole_transaction(engine):
    before=fingerprint(engine)
    with pytest.raises(IntegrityError):
        with engine.begin() as c:
            # Uncommitted reference insert, then intentional invalid FK.
            c.execute(Material.__table__.insert().values(id=2000000000,code='V2-ROLLBACK-PROBE',name='V2事务探针',unit='pcs',safety_stock=Decimal('1')))
            c.execute(SupplierMaterial.__table__.insert().values(supplier_id=1,material_id=1999999999,unit_price=Decimal('1'),lead_time_days=5,moq=Decimal('1'),package_multiple=Decimal('1'),capacity=Decimal('10')))
    assert fingerprint(engine)==before
