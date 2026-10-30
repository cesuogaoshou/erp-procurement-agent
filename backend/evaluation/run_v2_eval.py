"""Evaluate frozen V2 business labels without changing data or labels."""
import argparse
import json
import os
from collections import Counter
from decimal import Decimal
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from backend.app.db.session import create_sqlite_engine
from backend.app.db.import_v2_data import import_into_connection, validate_target
from backend.app.services.dataset_v2 import DEFAULT_OUTPUT, validate, write_json
from backend.app.services.recommendations import recommend_for_material


def evaluate(session, dataset=DEFAULT_OUTPUT):
    validate(dataset)
    cases=json.loads((Path(dataset)/'scenarios.json').read_text(encoding='utf-8'))
    details=[]
    for case in cases:
        result=recommend_for_material(session,case['material_id'],Decimal(case['quantity']),case['required_in_days'],Decimal(case['budget']))
        recs=result.recommendations
        labels=set(case['acceptable_supplier_ids'])
        ids=[r.supplier_id for r in recs]
        details.append(dict(**case, actual_top3=ids, top1_acceptable=bool(ids and ids[0] in labels),
            top3_hit=bool(set(ids)&labels), correct_rejection=not ids if not labels else None,
            recommendations=[dict(supplier_id=r.supplier_id,supplier_name=r.supplier_name,unit_price=r.unit_price,
                total_amount=r.total_amount,score=r.score,evidence=r.evidence) for r in recs],
            excluded=[dict(supplier_id=r.supplier_id,supplier_name=r.supplier_name,reasons=r.reasons) for r in result.excluded]))
    positive=[r for r in details if r['acceptable_supplier_ids']]
    negative=[r for r in details if not r['acceptable_supplier_ids']]
    top1=sum(r['top1_acceptable'] for r in positive); top3=sum(r['top3_hit'] for r in positive)
    return dict(version=validate(dataset)['version'],cases=len(details),positive_cases=len(positive),negative_cases=len(negative),
        top1_acceptable_count=top1, top3_hit_count=top3,
        top1_percent=round(top1/len(positive)*100,2),top3_percent=round(top3/len(positive)*100,2),
        correct_rejections=sum(r['correct_rejection'] for r in negative),
        qualified_candidate_counts=dict(Counter(len(r['eligible_supplier_ids']) for r in details)),
        top1_distribution=dict(Counter(r['recommendations'][0]['supplier_name'] for r in details if r['recommendations'])),
        failures=[r['case_id'] for r in positive if not r['top1_acceptable']]+[r['case_id'] for r in negative if not r['correct_rejection']],
        notes=['Labels frozen before generation; independent hard constraints and business thresholds.',
               'Top3 means any acceptable supplier, not exact best ranking.',
               'V1/V2 are different datasets; metric changes do not demonstrate algorithm improvement.',
               'Offline supplier evaluation does not test forecast shortage, model orchestration, or approval.'],details=details)


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--mysql',action='store_true')
    parser.add_argument('--output',default='reports/generated/v2_acceptance_20261029/supplier_eval_v2.json')
    args=parser.parse_args()
    if args.mysql:
        url=os.environ.get('V2_DATABASE_URL',''); validate_target(url)
        engine=create_engine(url,hide_parameters=True)
    else:
        engine=create_sqlite_engine('sqlite+pysqlite:///:memory:')
        with engine.begin() as c: import_into_connection(c)
    with Session(engine) as session: result=evaluate(session)
    engine.dispose()
    write_json(args.output,result)
    print(json.dumps({k:v for k,v in result.items() if k not in ('details','notes')},ensure_ascii=False))


if __name__=='__main__': main()
