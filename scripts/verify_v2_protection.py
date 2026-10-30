"""Read-only comparison against the pre-V2 protection snapshot."""
import argparse
import hashlib
import json
import os
from pathlib import Path

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import make_url

from backend.app.services.dataset_v2 import digest, write_json


def snapshot_database(engine):
    result={}
    with engine.connect() as c:
        for table in inspect(c).get_table_names():
            rows=[dict(r._mapping) for r in c.execute(text('SELECT * FROM `'+table+'`'))]
            encoded=sorted(json.dumps(r,default=str,sort_keys=True,ensure_ascii=False) for r in rows)
            result[table]={'count':len(rows),'sha256':hashlib.sha256('\n'.join(encoded).encode()).hexdigest()}
        result['order57']={t:[dict(r._mapping) for r in c.execute(text(q))] for t,q in {
            'order':'SELECT * FROM purchase_orders WHERE id=57',
            'items':'SELECT * FROM purchase_order_items WHERE order_id=57',
            'approval':'SELECT * FROM approval_records WHERE order_id=57'}.items()}
    return json.loads(json.dumps(result,default=str))


def main():
    parser=argparse.ArgumentParser(description='Read-only V1 protection check; never initializes any database.')
    parser.add_argument('--baseline',default='reports/generated/v2_acceptance_20261029/before.json')
    parser.add_argument('--output',default='reports/generated/v2_acceptance_20261029/protection.json')
    args=parser.parse_args()
    baseline=json.loads(Path(args.baseline).read_text(encoding='utf-8'))
    intentional={'frontend/src/App.vue','frontend/vite.config.ts'}
    intentional={s.replace('/',os.sep) for s in intentional}
    changed=[]
    for name,h in baseline['files'].items():
        current=digest(name) if Path(name).exists() else None
        if current!=h: changed.append(name)
    url=os.environ.get('DATABASE_URL','')
    if make_url(url).database!='erp_procurement':
        raise SystemExit('original_database_required_for_readonly_protection_check')
    engine=create_engine(url,hide_parameters=True)
    try: after=snapshot_database(engine)
    finally: engine.dispose()
    changes=[name for name in baseline['database'] if baseline['database'][name]!=after.get(name)]
    unexpected=[name for name in changed if name not in intentional]
    result=dict(passed=not changes and not unexpected, original_database_tables_unchanged=not changes,
        database_differences=changes, original_database_after=after, protected_file_count=len(baseline['files']),
        changed_existing_files=changed, allowed_existing_changes=sorted(intentional),unexpected_file_changes=unexpected,
        note='Full original database table digests include historical orders, approvals, executions, traces and audit rows. .env absence/presence and delivery bytes also checked.')
    write_json(args.output,result)
    print(json.dumps({k:v for k,v in result.items() if k!='original_database_after'},ensure_ascii=False))
    if not result['passed']: raise SystemExit(1)


if __name__=='__main__': main()
