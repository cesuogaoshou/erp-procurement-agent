"""Opt-in real-model V2 business acceptance; writes only to the isolated API."""
import argparse
import json
from decimal import Decimal
from pathlib import Path
from urllib.parse import urlparse

import requests

from backend.app.services.dataset_v2 import DEFAULT_OUTPUT, read_csv, write_json


def cases():
    labels=json.loads((DEFAULT_OUTPUT/'scenarios.json').read_text(encoding='utf-8'))
    rows=[]
    for material in read_csv(DEFAULT_OUTPUT/'materials.csv'):
        case=next(c for c in labels if c['material_id']==int(material['id']) and c['scenario']=='normal')
        unit='套' if material['unit']=='set' else '件'
        rows.append(dict(case_id=f"B{int(material['id']):02}",
            prompt=f"请采购120{unit}{material['name']}，20天内到货，总预算{case['budget']}元，先生成草稿等人工审批。",
            budget=case['budget'],expected='draft',acceptable_suppliers=case['acceptable_supplier_ids']))
    specs=[
        ('ECONOMY','请采购120件标准轴承，26天内到货，总预算950元，先生成草稿等人工审批。','950','draft',[3]),
        ('URGENT_ORIGINAL','紧急采购120件标准轴承，3天内到货，总预算2000元，先生成草稿等人工审批。','2000','draft',[4]),
        ('URGENT_SEAL','紧急采购20件密封圈，3天内到货，总预算100元，先生成草稿等人工审批。','100','draft',[4]),
        ('BULK','请采购600件包装托盘，40天内到货，总预算10000元，先生成草稿等人工审批。','10000','draft',[2,9]),
        ('MOQ','请采购5件标准轴承，20天内到货，总预算500元，先生成草稿等人工审批。','500','rounding',[]),
        ('PACK','请采购121件密封圈，20天内到货，总预算500元，先生成草稿等人工审批。','500','rounding',[]),
        ('PACK_CONFIRMED','我确认采购130件密封圈，20天内到货，总预算500元，先生成草稿等人工审批。','500','draft',[8,1,4,5,7,9]),
        ('MULTI','请采购120件标准轴承和80件铝合金外壳，20天内到货，整单总预算5000元，先生成草稿等人工审批。','5000','multi',[]),
        ('SHARED_TIGHT','请采购120件标准轴承和80件铝合金外壳，20天内到货，整单总预算2000元，先生成草稿等人工审批。','2000','shared_reject',[]),
        ('NO_BUDGET','请采购120件标准轴承，26天内到货，总预算1元，先生成草稿等人工审批。','1','reject',[]),
        ('NO_DELIVERY','请采购120件标准轴承，1天内到货，总预算2000元，先生成草稿等人工审批。','2000','reject',[]),
        ('NO_CAPACITY','请采购2500件包装托盘，180天内到货，总预算50000元，先生成草稿等人工审批。','50000','reject',[]),
        ('MONTH_KNOWN','帮我看看标准轴承未来一个月还缺多少，再比较一下合适的供应商。我现在只是了解情况，千万不要生成采购单。',None,'analysis',[]),
        ('DAYS_CONTROL','帮我看看标准轴承未来30天还缺多少，再比较一下合适的供应商。我现在只是了解情况，千万不要生成采购单。',None,'analysis',[]),
    ]
    rows.extend(dict(case_id=i,prompt=p,budget=b,expected=e,acceptable_suppliers=s) for i,p,b,e,s in specs)
    return rows


def run(api, output):
    parsed=urlparse(api)
    if parsed.hostname not in ('127.0.0.1','localhost') or parsed.port!=8002:
        raise ValueError('isolated_v2_api_required')
    client=requests.Session()
    env=client.get(api+'/environment',timeout=5).json()
    if env.get('environment')!='V2' or env.get('database')!='erp_procurement_demo_v2':
        raise ValueError('isolated_v2_api_required')
    client.headers['Authorization']='Bearer '+client.post(api+'/auth/login',json={'username':'buyer','password':'buyer-pass'},timeout=5).json()['access_token']
    output=Path(output);output.mkdir(parents=True,exist_ok=True)
    if (output/'business_results.json').exists():
        raise ValueError('existing_evidence_refused; choose a new --output directory')
    matrix=cases();write_json(output/'business_cases.json',matrix)
    results=[]
    for case in matrix:
        body={'prompt':case['prompt'],'total_budget':case['budget'],'use_langgraph':True}
        r=client.post(api+'/agent/runs',json=body,timeout=240)
        actual=r.json();phases=[actual]
        if r.status_code==200 and actual['status']=='awaiting_confirmation' and case['expected'] in ('draft','multi','shared_reject'):
            # Explicitly confirm the original unchanged complete request only.
            r=client.post(f"{api}/agent/runs/{actual['run_id']}/confirm",json=dict(prompt=case['prompt'],total_budget=case['budget'],confirmation_fingerprint=actual['confirmation_fingerprint']),timeout=240)
            actual=r.json();phases.append(actual)
        run_id=actual.get('run_id')
        traces=client.get(f'{api}/agent/runs/{run_id}/traces',timeout=10).json() if run_id else []
        order=next((o for o in client.get(api+'/purchase-orders',timeout=10).json() if o['id']==actual.get('purchase_order_id')),None)
        good=r.status_code==200
        if case['expected'] in ('draft','multi'):
            good=good and actual.get('status')=='draft_created' and bool(order)
            if order:
                good=good and Decimal(order['total_amount'])<=Decimal(case['budget']) and order['supplier_id']!=10
                if case['acceptable_suppliers']: good=good and order['supplier_id'] in case['acceptable_suppliers']
                if case['expected']=='multi': good=good and {i['material_name']:Decimal(i['quantity']) for i in order['items']}=={'标准轴承':Decimal(120),'铝合金外壳':Decimal(80)}
        elif case['expected']=='analysis':
            good=good and actual.get('purchase_order_id') is None and any(t.get('tool_name')=='recommend_suppliers' and t.get('status')=='ok' for t in traces)
        else:
            message=actual.get('business_message','')
            good=good and actual.get('purchase_order_id') is None and bool(message) and actual.get('status')!='awaiting_confirmation'
            if case['expected']=='rounding': good=good and any(w in message for w in ('确认','多买','包装','起订'))
            if case['expected']=='shared_reject':
                good=good and '整单共享预算不足' in message and '超过' in message
            elif case['expected']=='reject':
                good=good and actual.get('status')=='no_qualified_suppliers'
        result=dict(**case,http_status=r.status_code,actual=actual,phases=phases,traces=traces,order=order,passed=bool(good))
        results.append(result);write_json(output/'business_results.json',results)
        print(case['case_id'],actual.get('run_id'),actual.get('status'),'PASS' if good else 'FAIL',flush=True)
    return results


if __name__=='__main__':
    parser=argparse.ArgumentParser(description='Explicit real-model V2 acceptance; creates V2 demonstration records.')
    parser.add_argument('--api',default='http://127.0.0.1:8002')
    parser.add_argument('--output',default='reports/generated/v2_acceptance_20261029')
    args=parser.parse_args()
    run(args.api,args.output)
