import csv
import json
from pathlib import Path

import pytest
from sqlalchemy import func, select

from backend.app.db.session import create_sqlite_engine, session_scope
from backend.app.models import Material, SupplierMaterial
from backend.app.services.dataset_v2 import generate, validate, load_rows
from backend.app.db.import_v2_data import validate_target, import_into_connection, verify_dataset_loaded


def test_v2_reproducible_and_v1_invariants(tmp_path):
    a, b = tmp_path / 'a', tmp_path / 'b'
    generate(a)
    generate(b)
    assert {p.name: p.read_bytes() for p in a.iterdir()} == {p.name: p.read_bytes() for p in b.iterdir()}
    assert validate(a)['valid']
    for name in ['materials.csv', 'suppliers.csv', 'demand_history.csv', 'inventory_snapshots.csv', 'data_splits.csv']:
        assert (a / name).read_bytes() == (Path('data/raw') / name).read_bytes()


@pytest.mark.parametrize('field,value', [
    ('unit_price','0'), ('capacity','1'), ('lead_time_days','0'),
    ('moq','-1'), ('package_multiple','0'), ('unit_price','0.123'),
    ('supplier_id','999'), ('material_id','999'),
])
def test_v2_rejects_invalid_quote_even_with_updated_manifest(tmp_path, field, value):
    generate(tmp_path)
    path = tmp_path / 'supplier_materials.csv'
    rows = list(csv.DictReader(path.open(encoding='utf-8')))
    rows[0][field] = value
    with path.open('w', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=rows[0].keys()); writer.writeheader(); writer.writerows(rows)
    with pytest.raises(ValueError):
        validate(tmp_path, check_hashes=False)


@pytest.mark.parametrize('field,value', [('on_time_deliveries','101'),('accepted_quantity','10001'),('complaint_count','101'),('promised_deliveries','0')])
def test_v2_rejects_impossible_performance(tmp_path, field, value):
    generate(tmp_path)
    path = tmp_path / 'supplier_performance.csv'
    rows = list(csv.DictReader(path.open(encoding='utf-8')))
    rows[0][field] = value
    with path.open('w', encoding='utf-8', newline='') as f:
        writer=csv.DictWriter(f,fieldnames=rows[0].keys()); writer.writeheader(); writer.writerows(rows)
    with pytest.raises(ValueError): validate(tmp_path, check_hashes=False)


def test_v2_rejects_duplicate_and_corruption(tmp_path):
    generate(tmp_path)
    path=tmp_path/'supplier_materials.csv'
    with path.open('a',encoding='utf-8') as f: f.write(path.read_text(encoding='utf-8').splitlines()[1]+'\n')
    with pytest.raises(ValueError): validate(tmp_path)
    with pytest.raises(ValueError): validate(tmp_path,check_hashes=False)


@pytest.mark.parametrize('url', [
    'mysql+pymysql://u:p@localhost/erp_procurement',
    'mysql+pymysql://u:p@localhost/erp_procurement_demo_v2_backup',
    'sqlite:///erp_procurement_demo_v2',
    'mysql+pymysql://u:p@localhost/',
    'mysql+pymysql://u:p@localhost/erp_procurement_demo_v2?database=erp_procurement',
    'mysql+pymysql://u:p@localhost/erp_procurement_demo_v2?db=erp_procurement',
    'mysql+pymysql://u:p@localhost/erp_procurement_demo_v2?host=other',
    'mysql+mysqldb://u:p@localhost/erp_procurement_demo_v2',
])
def test_v2_target_strictly_scoped(url):
    with pytest.raises(ValueError,match='v2_target_required'): validate_target(url)
    validate_target('mysql+pymysql://u:p@localhost/erp_procurement_demo_v2')


def test_v2_import_empty_only_and_atomic_rollback(tmp_path):
    generate(tmp_path)
    engine=create_sqlite_engine('sqlite+pysqlite:///:memory:')
    with pytest.raises(RuntimeError,match='injected'):
        with engine.begin() as c:
            import_into_connection(c,tmp_path,after_insert=lambda: (_ for _ in ()).throw(RuntimeError('injected')))
    with engine.connect() as c:
        assert c.scalar(select(func.count()).select_from(Material)) == 0
    with engine.begin() as c: import_into_connection(c,tmp_path)
    with engine.begin() as c:
        with pytest.raises(ValueError,match='nonempty'): import_into_connection(c,tmp_path)
    with session_scope(engine) as s:
        assert s.scalar(select(func.count()).select_from(Material)) == 10
        assert s.scalar(select(func.count()).select_from(SupplierMaterial)) == 100


def test_v2_labels_are_frozen_business_conditions_and_cover_constraints(tmp_path):
    generate(tmp_path)
    cases=json.loads((tmp_path/'scenarios.json').read_text(encoding='utf-8'))
    assert len(cases)==80
    assert {c['material_id'] for c in cases}==set(range(1,11))
    assert any(len(c['acceptable_supplier_ids'])>1 for c in cases)
    assert any(len(c['acceptable_supplier_ids'])==1 for c in cases)
    assert any(not c['acceptable_supplier_ids'] for c in cases)
    assert all(10 not in c['acceptable_supplier_ids'] for c in cases)
    assert {tuple(c['acceptable_supplier_ids']) for c in cases if c['scenario']=='urgent'}=={(4,)}
    assert {tuple(c['acceptable_supplier_ids']) for c in cases if c['scenario']=='economy'}=={(3,)}


def test_v2_startup_requires_actual_imported_dataset(tmp_path):
    generate(tmp_path)
    engine=create_sqlite_engine('sqlite+pysqlite:///:memory:')
    with engine.begin() as c:
        with pytest.raises(ValueError,match='dataset_not_loaded'): verify_dataset_loaded(c,tmp_path)
        import_into_connection(c,tmp_path)
        verify_dataset_loaded(c,tmp_path)
        c.execute(SupplierMaterial.__table__.update().where(SupplierMaterial.supplier_id==1).values(unit_price=1))
        with pytest.raises(ValueError,match='dataset_not_loaded'): verify_dataset_loaded(c,tmp_path)


def test_v2_tradeoffs_and_rejection_reasons(tmp_path):
    from backend.evaluation.run_v2_eval import evaluate
    generate(tmp_path)
    engine=create_sqlite_engine('sqlite+pysqlite:///:memory:')
    with engine.begin() as c: import_into_connection(c,tmp_path)
    with session_scope(engine) as s: result=evaluate(s,tmp_path)
    normal=[c for c in result['details'] if c['scenario']=='normal']
    assert len({c['actual_top3'][0] for c in normal})>=3
    assert all(10 not in c['actual_top3'] for c in result['details'])
    reasons={r for c in result['details'] for excluded in c['excluded'] for r in excluded['reasons']}
    assert {'supplier_inactive','quantity_below_moq','lead_time_exceeds_required','capacity_below_quantity','budget_exceeded'}<=reasons


def test_v2_multiple_materials_enforce_shared_budget(tmp_path):
    from decimal import Decimal
    from backend.app.services.forecasting import get_demand_forecast
    from backend.app.services.purchase_drafts import PurchaseDraftInput, DraftItemInput, create_purchase_draft
    generate(tmp_path)
    engine=create_sqlite_engine('sqlite+pysqlite:///:memory:')
    with engine.begin() as c: import_into_connection(c,tmp_path)
    with session_scope(engine) as s:
        by_name={m.name:m.id for m in s.scalars(select(Material))}
        items=[DraftItemInput(by_name['标准轴承'],Decimal(120)),DraftItemInput(by_name['铝合金外壳'],Decimal(80))]
        refs=[get_demand_forecast(s,item.material_id,20)['evidence_ref'] for item in items]
        refs += [f'recommendation:{item.material_id}:1:{item.quantity}:20:none' for item in items]
        with pytest.raises(ValueError,match='order_budget_exceeded'):
            create_purchase_draft(s,PurchaseDraftInput(1,items,'v2-multi-tight-budget',refs,total_budget=Decimal(2000)))
        order=create_purchase_draft(s,PurchaseDraftInput(1,items,'v2-multi-enough-budget',refs,total_budget=Decimal(5000)))
        assert order.total_amount==Decimal('3441.60')
        assert len(order.items)==2
