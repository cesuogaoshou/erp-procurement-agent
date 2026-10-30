"""Read-only supplier-side comparison and invariant proof."""
import argparse
from decimal import Decimal
from pathlib import Path

from backend.app.services.dataset_v2 import V1, DEFAULT_OUTPUT, INVARIANTS, read_csv, digest, validate, write_json


def compare():
    validate()
    invariant={name:{'v1_sha256':digest(V1/name),'v2_sha256':digest(DEFAULT_OUTPUT/name),
        'byte_identical':(V1/name).read_bytes()==(DEFAULT_OUTPUT/name).read_bytes()} for name in INVARIANTS}
    result={'version':'simulated_procurement_v2_20261029.1','invariants':invariant,'changed_tables':{}}
    for table in ('supplier_materials','supplier_performance'):
        old={(r['supplier_id'],r['material_id']):r for r in read_csv(V1/(table+'.csv'))}
        new={(r['supplier_id'],r['material_id']):r for r in read_csv(DEFAULT_OUTPUT/(table+'.csv'))}
        changes=[]
        for key in old:
            changed={k:{'v1':v,'v2':new[key][k]} for k,v in old[key].items() if v!=new[key][k]}
            if changed: changes.append({'supplier_id':key[0],'material_id':key[1],'fields':changed})
        result['changed_tables'][table]={'v1_rows':len(old),'v2_rows':len(new),'changed_rows':len(changes),'details':changes}
    return result


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--output',default='reports/generated/v2_acceptance_20261029/v1_v2_comparison.json')
    args=parser.parse_args()
    result=compare();write_json(args.output,result)
    print('invariants:',all(r['byte_identical'] for r in result['invariants'].values()),
          'changed rows:',{k:v['changed_rows'] for k,v in result['changed_tables'].items()})
