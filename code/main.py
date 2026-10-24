#!/usr/bin/env python3
"""Run the deletion audit from any working directory."""
import argparse
from collections import Counter
from dataclasses import asdict
import hashlib
import json
import os
from pathlib import Path
import sys
import time
import csv
from ghost_audit.schema import AuditError, read_csv, HEADER, natural_key
from ghost_audit.ingest import EvidenceStore
from ghost_audit.engine import Auditor

ROOT=Path(__file__).resolve().parents[1]

def run(dataset,requests,output,cache=None,no_cache=False,case_sort='lexical',images=True,diagnostics=None,allow_errors=False):
    started=time.perf_counter()
    store=EvidenceStore(dataset,cache,no_cache,images)
    engine=Auditor(store,read_csv(dataset/'user_identities.csv'),read_csv(dataset/'user_audit_log.csv'),read_csv(dataset/'deletion_rules.csv'))
    cases=read_csv(requests)
    if len({r['case_id'] for r in cases})!=len(cases):raise AuditError('Duplicate request IDs')
    key=(lambda r:r['case_id']) if case_sort=='lexical' else (lambda r:natural_key(r['case_id']))
    rows=[];details=[];errors=[]
    for request in sorted(cases,key=key):
        t=time.perf_counter()
        try:
            status,steps,detail=engine.investigate(request)
            detail['elapsed_seconds']=round(time.perf_counter()-t,6)
            rows.append(dict(case_id=request['case_id'],deletion_status=status,steps_json=json.dumps(steps,ensure_ascii=False,separators=(',',':'))))
            details.append(detail)
        except AuditError as e:
            errors.append({'case_id':request['case_id'],'error':str(e)})
    report={'requests':len(cases),'produced':len(rows),'errors':errors,'status_distribution':dict(Counter(r['deletion_status'] for r in rows)),'operations':dict(Counter(s['operation'] for r in rows for s in json.loads(r['steps_json']))),'evidence_files':len(store.manifest),'observations':len(store.observations),'extraction_diagnostics':store.diagnostics,'ocr_calls':store.ocr_calls,'ocr_cache_hits':store.ocr_cache_hits,'llm_calls':0,'input_tokens':0,'output_tokens':0,'api_cost_usd':0,'elapsed_seconds':round(time.perf_counter()-started,3),'hash_algorithm_verified':engine.identity.hash_verified,'cases':details}
    if diagnostics:
        diagnostics.parent.mkdir(parents=True,exist_ok=True);diagnostics.write_text(json.dumps(report,ensure_ascii=False,indent=2))
    if errors and not allow_errors:
        raise AuditError(f'{len(errors)}/{len(cases)} unresolved cases; output not replaced. First errors: {errors[:5]}. See diagnostics.')
    output.parent.mkdir(parents=True,exist_ok=True)
    temp=output.with_suffix('.tmp')
    with temp.open('w',encoding='utf-8',newline='') as f:
        w=csv.DictWriter(f,fieldnames=HEADER);w.writeheader();w.writerows(rows)
    temp.replace(output)
    return rows,report

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--dataset',type=Path,default=ROOT/'dataset')
    p.add_argument('--requests',type=Path)
    p.add_argument('--output',type=Path,default=ROOT/'output.csv')
    p.add_argument('--diagnostics',type=Path,default=ROOT/'evaluation_runs/final_run.json')
    p.add_argument('--cache',type=Path,default=ROOT/'.cache/ocr')
    p.add_argument('--no-cache',action='store_true')
    p.add_argument('--case-sort',choices=['lexical','natural'],default='lexical')
    p.add_argument('--no-images',action='store_true',help='Ablation only; not submission mode')
    args=p.parse_args()
    try:
        _,r=run(args.dataset,args.requests or args.dataset/'deletion_requests.csv',args.output,args.cache,args.no_cache,args.case_sort,not args.no_images,args.diagnostics)
        print(json.dumps({k:v for k,v in r.items() if k not in {'cases','extraction_diagnostics'}},indent=2))
    except (AuditError,FileNotFoundError) as e:print(f'AUDIT FAILED: {e}',file=sys.stderr);sys.exit(2)

if __name__=='__main__':main()
