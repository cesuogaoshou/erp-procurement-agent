"""Reproducible, independently labeled teaching simulation. Never writes V1."""
import csv
import hashlib
import json
import shutil
from datetime import date, datetime
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
from random import Random

ROOT = Path(__file__).resolve().parents[3]
DESIGN = ROOT / 'data/v2/design.json'
V1 = ROOT / 'data/raw'
DEFAULT_OUTPUT = ROOT / 'data/v2/raw'
INVARIANTS = ('materials.csv', 'suppliers.csv', 'demand_history.csv', 'inventory_snapshots.csv', 'data_splits.csv')
CENT = Decimal('0.01')


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read_csv(path):
    with Path(path).open(encoding='utf-8', newline='') as f:
        return list(csv.DictReader(f))


def write_json(path, value):
    Path(path).write_text(json.dumps(value, ensure_ascii=False, indent=2, default=str) + '\n', encoding='utf-8')


def money(value):
    return str(Decimal(value).quantize(CENT, rounding=ROUND_HALF_UP))


def _write_csv(path, rows):
    with Path(path).open('w', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def generate(output=DEFAULT_OUTPUT):
    output = Path(output).resolve()
    if output == V1.resolve() or V1.resolve() in output.parents:
        raise ValueError('v1_write_forbidden')
    config = json.loads(DESIGN.read_text(encoding='utf-8'))
    rng = Random(config['seed'])  # independent; never invoke seed_demo_data
    output.mkdir(parents=True, exist_ok=True)
    for name in INVARIANTS:
        shutil.copyfile(V1 / name, output / name)
    quotes, performances = [], []
    for m, base in enumerate(config['base_prices'], 1):
        for profile in config['profiles']:
            side = 0 if m in profile['specialties'] else 1
            price = Decimal(base) * Decimal(profile['price'][side])
            quotes.append(dict(supplier_id=profile['supplier_id'], material_id=m,
                unit_price=money(price), lead_time_days=profile['days'][side],
                moq=money(profile['moq']),
                package_multiple=money(max(profile['pack'], config['packaging'].get(str(m), 1))),
                capacity=money(profile['capacity'][side])))
            on_time, accepted, complaints = profile['performance'][side]
            performances.append(dict(supplier_id=profile['supplier_id'], material_id=m,
                observed_until=config['observation_date'],
                avg_price=money(price * Decimal(rng.randint(97, 103)) / 100),
                promised_deliveries=100, on_time_deliveries=on_time,
                inspected_quantity='10000.00', accepted_quantity=money(accepted), complaint_count=complaints))
    _write_csv(output / 'supplier_materials.csv', quotes)
    _write_csv(output / 'supplier_performance.csv', performances)
    write_json(output / 'scenarios.json', build_scenarios(output, config))
    files = {}
    for name in (*INVARIANTS, 'supplier_materials.csv', 'supplier_performance.csv', 'scenarios.json'):
        files[name] = {'sha256': digest(output / name), 'rows':
            len(read_csv(output / name)) if name.endswith('.csv') else len(json.loads((output/name).read_text(encoding='utf-8')))}
    write_json(output / 'manifest.json', dict(version=config['version'], seed=config['seed'],
        design_date=config['design_date'], observation_date=config['observation_date'],
        source=config['source'], generator='backend.app.services.dataset_v2',
        generator_sha256=digest(__file__), design_sha256=digest(DESIGN), parameters=config,
        source_v1_sha256={f.name:digest(f) for f in sorted(V1.iterdir()) if f.is_file()},
        invariant_files=list(INVARIANTS), files=files,
        primary_keys={'materials':['id'], 'suppliers':['id'], 'inventory_snapshots':['material_id'],
            'demand_history':['material_id','demand_date'], 'supplier_materials':['supplier_id','material_id'],
            'supplier_performance':['supplier_id','material_id','observed_until']},
        label_policy='independent_hard_constraints_and_business_thresholds; never weighted scoring'))
    return validate(output)


def build_scenarios(output, config):
    """Independent business oracle; intentionally imports no recommendation code."""
    quotes = read_csv(output / 'supplier_materials.csv')
    perf = {(r['supplier_id'],r['material_id']):r for r in read_csv(output/'supplier_performance.csv')}
    active = {r['id'] for r in read_csv(output/'suppliers.csv') if r['active']=='True'}
    cases = []
    for m, base in enumerate(config['base_prices'],1):
        for spec in config['scenarios']:
            qty=Decimal(spec['quantity'])
            budget=Decimal(spec['budget']) if 'budget' in spec else Decimal(base)*qty*Decimal(spec['budget_factor'])
            labels, eligible = [], []
            for q in quotes:
                if int(q['material_id'])!=m or q['supplier_id'] not in active:
                    continue
                if not (Decimal(q['moq'])<=qty<=Decimal(q['capacity']) and int(q['lead_time_days'])<=spec['days']
                        and qty*Decimal(q['unit_price'])<=budget and qty%Decimal(q['package_multiple'])==0):
                    continue
                eligible.append(int(q['supplier_id']))
                p=perf[q['supplier_id'],q['material_id']]
                otd=Decimal(p['on_time_deliveries'])/Decimal(p['promised_deliveries'])
                quality=Decimal(p['accepted_quantity'])/Decimal(p['inspected_quantity'])
                complaint=Decimal(p['complaint_count'])/Decimal(p['promised_deliveries'])
                if otd>=Decimal(spec.get('min_on_time','0')) and quality>=Decimal(spec.get('min_quality','0')) and complaint<=Decimal(spec.get('max_complaint','1')):
                    labels.append(int(q['supplier_id']))
            cases.append(dict(case_id=f"V2-M{m:02d}-{spec['name']}", material_id=m, scenario=spec['name'],
                quantity=money(qty),required_in_days=spec['days'],budget=money(budget),
                acceptable_supplier_ids=labels, eligible_supplier_ids=eligible, label_conditions=spec,
                label_source='frozen_business_conditions_v2_20261029'))
    return cases


def _require(condition, message):
    if not condition:
        raise ValueError('v2_invalid:' + message)


def _number(row, key, positive=False):
    try:
        n=Decimal(row[key])
        _require(n.is_finite() and n>=0 and n<Decimal('10000000000') and n==n.quantize(CENT), 'precision:'+key)
        if positive: _require(n>0,'positive:'+key)
        return n
    except (ArithmeticError, KeyError):
        raise ValueError('v2_invalid:number:'+key) from None


def validate(output=DEFAULT_OUTPUT, *, check_hashes=True):
    output=Path(output)
    manifest=json.loads((output/'manifest.json').read_text(encoding='utf-8'))
    config=json.loads(DESIGN.read_text(encoding='utf-8'))
    _require(manifest['version']==config['version'] and manifest['design_sha256']==digest(DESIGN),'version_or_design')
    _require(manifest['parameters']==config,'parameters')
    for name, h in manifest['source_v1_sha256'].items():
        _require(digest(V1/name)==h,'v1_changed:'+name)
    for name in INVARIANTS:
        _require((output/name).read_bytes()==(V1/name).read_bytes(),'invariant:'+name)
    for name, meta in manifest['files'].items():
        if check_hashes: _require(digest(output/name)==meta['sha256'],'hash:'+name)
        rows=read_csv(output/name) if name.endswith('.csv') else json.loads((output/name).read_text(encoding='utf-8'))
        _require(len(rows)==meta['rows'],'row_count:'+name)
    materials={r['id'] for r in read_csv(output/'materials.csv')}
    suppliers={r['id'] for r in read_csv(output/'suppliers.csv')}
    for table, keys in manifest['primary_keys'].items():
        rows=read_csv(output/(table+'.csv'))
        identities=[tuple(r[k] for k in keys) for r in rows]
        _require(len(identities)==len(set(identities)), 'duplicate:'+table)
        for r in rows:
            if 'material_id' in r: _require(r['material_id'] in materials,'material_fk')
            if 'supplier_id' in r: _require(r['supplier_id'] in suppliers,'supplier_fk')
    quotes=read_csv(output/'supplier_materials.csv')
    perfs=read_csv(output/'supplier_performance.csv')
    expected={(s,m) for s in suppliers for m in materials}
    _require({(q['supplier_id'],q['material_id']) for q in quotes}==expected,'quote_coverage')
    _require({(q['supplier_id'],q['material_id']) for q in perfs}==expected,'performance_coverage')
    for q in quotes:
        for k in ('unit_price','moq','package_multiple','capacity'): _number(q,k,True)
        _require(1<=int(q['lead_time_days'])<=90,'lead_time')
        minimum=(_number(q,'moq')/_number(q,'package_multiple')).to_integral_value(rounding='ROUND_CEILING')*_number(q,'package_multiple')
        _require(minimum<=_number(q,'capacity'),'unusable_capacity')
    for p in perfs:
        promised=int(p['promised_deliveries']); on_time=int(p['on_time_deliveries']); complaints=int(p['complaint_count'])
        _require(promised>0 and 0<=on_time<=promised and 0<=complaints<=promised,'delivery_or_complaint')
        inspected=_number(p,'inspected_quantity',True); accepted=_number(p,'accepted_quantity')
        _require(accepted<=inspected and Decimal(complaints)<=inspected-accepted,'quality_or_complaint')
        _number(p,'avg_price',True)
        _require(date.fromisoformat(p['observed_until'])==date.fromisoformat(config['observation_date']),'observed_date')
    cases=json.loads((output/'scenarios.json').read_text(encoding='utf-8'))
    _require(cases==build_scenarios(output,config),'labels')
    return dict(valid=True, version=manifest['version'], files=manifest['files'], invariant_files=list(INVARIANTS))


def load_rows(output=DEFAULT_OUTPUT):
    """Typed records; database identities for relations remain auto-generated."""
    from backend.app.models import Material, Supplier, Inventory, DemandHistory, SupplierMaterial, SupplierPerformance
    result=[]
    for name, model in [('materials',Material),('suppliers',Supplier),('inventory_snapshots',Inventory),
                        ('demand_history',DemandHistory),('supplier_materials',SupplierMaterial),('supplier_performance',SupplierPerformance)]:
        rows=[]
        for r in read_csv(Path(output)/(name+'.csv')):
            converted={}
            for k,v in r.items():
                if k=='snapshot_date': converted['updated_at']=datetime.fromisoformat(v); continue
                if k=='inbound_confirmed': continue
                if k in ('id','material_id','supplier_id','version','lead_time_days','promised_deliveries','on_time_deliveries','complaint_count'): v=int(v)
                elif k=='active': v=v=='True'
                elif k in ('demand_date','observed_until'): v=date.fromisoformat(v)
                elif k not in ('code','name','unit'): v=Decimal(v)
                converted[k]=v
            rows.append(converted)
        result.append((model.__table__,rows))
    return result
