#!/usr/bin/env python3
"""Strict structural validation plus fresh reconstruction from participant evidence."""
import argparse,csv,json
from pathlib import Path
from ghost_audit.schema import AuditError,HEADER,read_csv,validate_steps
from ghost_audit.provenance import dataset_digest,behavior_digest,sha
from ghost_audit.ingest import EvidenceStore
from ghost_audit.engine import Auditor
from main import ROOT

def validate(output,dataset,diagnostics,partial=False,allow_degraded=False,requests=None):
    with output.open(newline='') as f:
        reader=csv.DictReader(f)
        if tuple(reader.fieldnames or [])!=HEADER:raise AuditError('Incorrect output header')
        rows=list(reader)
    request_path=requests or dataset/'deletion_requests.csv'
    queries={r['case_id']:r for r in read_csv(request_path)}
    ids=[r['case_id'] for r in rows]
    if len(ids)!=len(set(ids)) or ids!=sorted(ids):raise AuditError('Duplicate or non-lexical case order')
    if not set(ids)<=set(queries):raise AuditError('Unknown case IDs')
    if not partial and set(ids)!=set(queries):raise AuditError(f'Incomplete output: {len(ids)}/{len(queries)} cases')
    report=json.loads(diagnostics.read_text())
    expected={'dataset_sha256':dataset_digest(dataset),'requests_sha256':sha(request_path),'behavior_sha256':behavior_digest(),'output_sha256':sha(output)}
    if report.get('bindings')!=expected:raise AuditError('Stale or mismatched dataset/output/behavior diagnostics')
    if report.get('images_enabled') is False and any(Path(r['file_path']).suffix=='.png' for r in read_csv(dataset/'evidence_files.csv')):
        raise AuditError('Image ablation cannot be validated as a submission')
    details={d['case_id']:d for d in report['cases']}
    if len(details)!=len(report['cases']):raise AuditError('Duplicate diagnostic cases')
    if not set(ids)<=set(details):raise AuditError('Missing diagnostic cases')
    store=EvidenceStore(dataset,ROOT/'.cache/ocr')
    auditor=Auditor(store,read_csv(dataset/'user_identities.csv'),read_csv(dataset/'user_audit_log.csv'),read_csv(dataset/'deletion_rules.csv'))
    for row in rows:
        cid=row['case_id'];detail=details[cid]
        try:steps=json.loads(row['steps_json'])
        except (ValueError,TypeError):raise AuditError(f'{cid}: Invalid JSON array') from None
        try:status,required,actual=auditor.investigate(queries[cid])
        except AuditError as error:
            if not allow_degraded:raise AuditError(f'{cid}: unresolved investigation: {error}') from None
            if row['deletion_status']!='INCOMPLETE' or steps!=[] or not detail.get('fallback') or detail.get('reason')!=str(error):
                raise AuditError(f'{cid}: invalid degraded review representation')
            actual=getattr(error,'diagnostic',{})
            for field in ['resources','partial_steps']:
                if detail.get(field,[])!=actual.get(field,[]):raise AuditError(f'{cid}: partial provenance mismatch')
            continue
        validate_steps(row['deletion_status'],steps)
        if row['deletion_status']!=status or steps!=required:
            raise AuditError(f'{cid}: authorization, policy, state, or complete plan differs from eligible source evidence')
        for field in ['subject','intent','resources']:
            if detail.get(field)!=json.loads(json.dumps(actual.get(field))):raise AuditError(f'{cid}: diagnostic {field} differs from reconstructed evidence')
        if detail.get('fallback'):raise AuditError(f'{cid}: resolved result marked degraded')
    return len(rows)

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output',type=Path,default=ROOT/'output.csv');p.add_argument('--dataset',type=Path,default=ROOT/'dataset')
    p.add_argument('--diagnostics',type=Path,default=ROOT/'evaluation_runs/final_run.json');p.add_argument('--requests',type=Path)
    p.add_argument('--partial',action='store_true');p.add_argument('--allow-degraded',action='store_true',help='Validate review representation only, never submission readiness')
    p.add_argument('--require-resolved',action='store_true',help='Compatibility flag; strict is now the default')
    a=p.parse_args()
    if a.allow_degraded and a.require_resolved:p.error('Conflicting strict/review validation flags')
    n=validate(a.output,a.dataset,a.diagnostics,a.partial,a.allow_degraded,a.requests)
    print(f'Validated {n} rows: '+('REVIEW ONLY; unresolved cases are not submission-ready' if a.allow_degraded or a.partial else 'strict source-reconstructed semantic checks passed'))
if __name__=='__main__':main()
