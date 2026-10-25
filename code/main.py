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
from ghost_audit.schema import AuditError, read_csv, HEADER, natural_key, timestamp
from ghost_audit.ingest import EvidenceStore
from ghost_audit.engine import Auditor
from ghost_audit.provenance import dataset_digest, behavior_digest, sha
from dotenv import load_dotenv

ROOT=Path(__file__).resolve().parents[1]

def load_environment(root=ROOT):
    """Load local credentials without replacing environment-provided values."""
    load_dotenv(root/'.env', override=False, interpolate=False)

def run(dataset,requests,output,cache=None,no_cache=False,case_sort='lexical',images=True,diagnostics=None,allow_errors=False,degraded=False):
    """Audit every request. ``degraded`` emits a best-effort row for unresolved cases.

    The library default is strict. ``main.py`` defaults to degraded because the
    documented command must produce a 518-row answer; ``--strict`` opts into the
    fail-closed gate.
    """
    load_environment()
    if allow_errors and output.resolve()==(ROOT/'output.csv').resolve():
        raise AuditError('Partial review output cannot overwrite root output.csv')
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
            detail=getattr(e,'diagnostic',{'case_id':request['case_id']})
            detail.update(fallback=True,reason=str(e),elapsed_seconds=round(time.perf_counter()-t,6))
            detail.setdefault('resources',[])
            details.append(detail)
            if degraded:
                rows.append(dict(case_id=request['case_id'],deletion_status='INCOMPLETE',steps_json='[]'))
    report={'requests':len(cases),'produced':len(rows),'errors':errors,'status_distribution':dict(Counter(r['deletion_status'] for r in rows)),'operations':dict(Counter(s['operation'] for r in rows for s in json.loads(r['steps_json']))),'evidence_files':len(store.manifest),'observations':len(store.observations),'extraction_diagnostics':store.diagnostics,'ocr_calls':store.ocr_calls,'ocr_cache_hits':store.ocr_cache_hits,'llm_calls':0,'input_tokens':0,'output_tokens':0,'api_cost_usd':0,'elapsed_seconds':round(time.perf_counter()-started,3),'hash_algorithm_verified':engine.identity.hash_verified,'cases':details}
    report['identity_warning_count']=sum(len(d.get('identity_warnings',[])) for d in details)
    report['cache_mode']='cold (cache reads disabled)' if no_cache or cache is None else 'cache enabled; see fresh/cached counts'
    report['fallback_count']=len(errors) if degraded else 0
    report['fallback_policy']='INCOMPLETE with empty steps; unproven, manual review required' if degraded else None
    report['degraded']=bool(degraded)
    report['strict']=not degraded
    report['bindings']={'dataset_sha256':dataset_digest(dataset),'requests_sha256':sha(requests),'behavior_sha256':behavior_digest()}
    report['requests_file']=str(Path(requests).resolve())
    report['images_enabled']=images
    report['submission_ready']=not errors and not degraded and not allow_errors
    if errors and not allow_errors and not degraded:
        if diagnostics:
            failed=diagnostics.with_name(diagnostics.stem+'.failed.json')
            failed.parent.mkdir(parents=True,exist_ok=True);failed.write_text(json.dumps(report,ensure_ascii=False,indent=2))
        raise AuditError(f'{len(errors)}/{len(cases)} unresolved; existing output and diagnostics preserved. See separate failed-run diagnostics.')
    output.parent.mkdir(parents=True,exist_ok=True)
    temp=output.with_suffix('.tmp')
    with temp.open('w',encoding='utf-8',newline='') as f:
        w=csv.DictWriter(f,fieldnames=HEADER);w.writeheader();w.writerows(rows)
    temp.replace(output)
    report['bindings']['output_sha256']=sha(output)
    if diagnostics:
        diagnostics.parent.mkdir(parents=True,exist_ok=True);diagnostics.write_text(json.dumps(report,ensure_ascii=False,indent=2))
    return rows,report

def warning_banner(report):
    bar='#'*72
    return (f"{bar}\n"
        f"# WARNING: DEGRADED OUTPUT — NOT A VERIFIED SUBMISSION\n"
        f"# {report['fallback_count']} of {report['requests']} cases could not be resolved.\n"
        f"# They are written as INCOMPLETE with steps_json=[] and listed in degraded_cases.md.\n"
        f"# Re-run with --strict to require full resolution (it exits 2 and keeps the prior file).\n"
        f"{bar}")

def write_degraded(report,path):
    cases=[d for d in report['cases'] if d.get('fallback')]
    text='# Degraded cases\n\n'
    text+=f'{len(cases)} unresolved cases retain `steps_json=[]`. Their `INCOMPLETE` status is a fallback guess, not an evidence-backed finding. No dummy steps or identifiers are inserted.\n\n'
    text+='| Case | Resolved subject | Unresolved cause |\n|---|---|---|\n'
    for d in cases:
        reason=d['reason'].replace('|','/').replace('\n',' ')
        text+=f"| {d['case_id']} | {d.get('subject','unresolved')} | {reason} |\n"
    path.write_text(text,encoding='utf-8')


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--dataset',type=Path,default=ROOT/'dataset')
    p.add_argument('--requests',type=Path)
    p.add_argument('--output',type=Path)
    p.add_argument('--diagnostics',type=Path)
    p.add_argument('--cache',type=Path,default=ROOT/'.cache/ocr')
    p.add_argument('--no-cache',action='store_true')
    p.add_argument('--case-sort',choices=['lexical','natural'],default='lexical')
    p.add_argument('--no-images',action='store_true',help='Ablation only; not submission mode')
    p.add_argument('--strict',action='store_true',help='Require every case to resolve; exits 2 and preserves the prior output otherwise')
    p.add_argument('--allow-degraded',action='store_true',help='Compatibility alias; degraded output is the default')
    p.add_argument('--review',action='store_true',help='Write the degraded artifact under the review directory instead of the root output')
    args=p.parse_args()
    if args.strict and (args.review or args.allow_degraded):p.error('--strict cannot be combined with --review or --allow-degraded')
    degraded=not args.strict
    args.output=args.output or (ROOT/'evaluation_runs/review/degraded_output.csv' if args.review else ROOT/'output.csv')
    args.diagnostics=args.diagnostics or (ROOT/'evaluation_runs/review/diagnostics.json' if args.review else ROOT/'evaluation_runs/final_run.json')
    try:
        _,r=run(args.dataset,args.requests or args.dataset/'deletion_requests.csv',args.output,args.cache,args.no_cache,args.case_sort,not args.no_images,args.diagnostics,degraded=degraded)
        if degraded:write_degraded(r,args.output.parent/'degraded_cases.md')
        print(json.dumps({k:v for k,v in r.items() if k not in {'cases','extraction_diagnostics','errors'}},indent=2))
        if degraded and r['errors']:print(warning_banner(r),file=sys.stderr)
    except (AuditError,FileNotFoundError) as e:print(f'AUDIT FAILED: {e}',file=sys.stderr);sys.exit(2)

if __name__=='__main__':main()
