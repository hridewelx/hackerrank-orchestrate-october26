#!/usr/bin/env python3
"""Export all cases for human review; this deliberately is NOT a submission output."""
import csv
import json
from pathlib import Path
import argparse
from main import ROOT, run
from ghost_audit.schema import read_csv


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--dataset',type=Path,default=ROOT/'dataset');p.add_argument('--no-cache',action='store_true');p.add_argument('--directory',type=Path,default=ROOT/'evaluation_runs/review');a=p.parse_args()
    a.directory.mkdir(parents=True,exist_ok=True)
    rows,report=run(a.dataset,a.dataset/'deletion_requests.csv',a.directory/'partial_predictions.csv',cache=ROOT/'.cache/ocr',no_cache=a.no_cache,diagnostics=a.directory/'diagnostics.json',allow_errors=True)
    known={r['case_id']:r for r in rows};errors={r['case_id']:r['error'] for r in report['errors']}
    with (a.directory/'case_review.csv').open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=['case_id','execution_status','deletion_status','steps_json','issue']);w.writeheader()
        for q in sorted(read_csv(a.dataset/'deletion_requests.csv'),key=lambda x:x['case_id']):
            r=known.get(q['case_id']);w.writerow({'case_id':q['case_id'],'execution_status':'RESOLVED' if r else 'UNRESOLVED','deletion_status':r['deletion_status'] if r else '', 'steps_json':r['steps_json'] if r else '', 'issue':errors.get(q['case_id'],'')})
    print(json.dumps({k:v for k,v in report.items() if k not in {'cases','extraction_diagnostics','errors'}},indent=2))
    print(f"Review only: {len(report['errors'])} unresolved. No submission output produced.")
if __name__=='__main__':main()
