#!/usr/bin/env python3
"""Validate output structure, coverage, citation times and emitted provenance."""
import argparse
import csv
import json
from pathlib import Path
from ghost_audit.schema import AuditError, HEADER, read_csv, timestamp, validate_steps
from main import ROOT


def validate(output,dataset,diagnostics,partial=False):
    with output.open(newline='') as f:
        reader=csv.DictReader(f)
        if tuple(reader.fieldnames or [])!=HEADER:raise AuditError('Incorrect output header')
        rows=list(reader)
    requests={r['case_id']:r for r in read_csv(dataset/'deletion_requests.csv')}
    ids=[r['case_id'] for r in rows]
    if len(ids)!=len(set(ids)) or ids!=sorted(ids):raise AuditError('Duplicate or non-lexical case order')
    if not set(ids)<=set(requests):raise AuditError('Unknown case IDs')
    if not partial and set(ids)!=set(requests):raise AuditError(f'Incomplete output: {len(ids)}/{len(requests)} cases')
    manifest={r['file_id']:r['captured_at'] for r in read_csv(dataset/'evidence_files.csv')}
    manifest.update({r['activity_id']:r['event_time'] for r in read_csv(dataset/'system_activity.csv')})
    manifest.update({r['audit_id']:r['event_time'] for r in read_csv(dataset/'user_audit_log.csv')})
    provenance={r['case_id']:r for r in json.loads(diagnostics.read_text())['cases']}
    for r in rows:
        steps=json.loads(r['steps_json']);validate_steps(r['deletion_status'],steps)
        cutoff=timestamp(requests[r['case_id']]['audit_at'])
        sources=provenance.get(r['case_id'],{}).get('resources',[])
        for step in steps:
            if not step['evidence_id']:continue
            evidence=step['evidence_id']
            if evidence not in manifest or timestamp(manifest[evidence])>cutoff:raise AuditError('Invalid/late citation')
            supporting=[s for s in sources if s['resource']==step['resource_id'] and s['system']==step['system_id'] and s['evidence']==evidence and timestamp(s['capture'])<=cutoff and timestamp(s['observed'])<=cutoff and s['locator']]
            if not supporting:raise AuditError('Citation lacks eligible resource/locator provenance')
    return len(rows)

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,default=ROOT/'output.csv');p.add_argument('--dataset',type=Path,default=ROOT/'dataset');p.add_argument('--diagnostics',type=Path,default=ROOT/'evaluation_runs/final_run.json');p.add_argument('--partial',action='store_true');a=p.parse_args()
    n=validate(a.output,a.dataset,a.diagnostics,a.partial)
    print(f'Validated {n} rows'+(' (partial review only)' if a.partial else ''))
if __name__=='__main__':main()
