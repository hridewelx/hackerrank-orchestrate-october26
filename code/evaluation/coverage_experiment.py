#!/usr/bin/env python3
"""Measure the account-coverage waiver experiment on the public samples.

Runs the same participant evidence through the same auditor with three coverage
policies and reports status accuracy, step precision/recall/F1 and whole-case
exactness. Nothing here selects a policy automatically; it exists to document the
adoption decision recorded in the evaluation report.
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from ghost_audit.engine import Auditor
from ghost_audit.ingest import EvidenceStore
from ghost_audit.schema import AuditError, read_csv
from evaluation.main import compare

ROOT = Path(__file__).resolve().parents[2]
WARNINGS = {'none': 0, 'retained': 0, 'compliant': 0}


def run_policy(dataset, policy, cache):
    store = EvidenceStore(dataset, cache, False, True)
    auditor = Auditor(store, read_csv(dataset / 'user_identities.csv'), read_csv(dataset / 'user_audit_log.csv'),
                      read_csv(dataset / 'deletion_rules.csv'), coverage_waiver=policy)
    rows = []
    for request in sorted(read_csv(dataset / 'sample_deletion_requests.csv'), key=lambda r: r['case_id']):
        try:
            status, steps, _ = auditor.investigate(request)
        except AuditError:
            status, steps = 'INCOMPLETE', []
        rows.append(dict(case_id=request['case_id'], deletion_status=status,
                         steps_json=json.dumps(steps, ensure_ascii=False, separators=(',', ':'))))
    return rows


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--dataset', type=Path, default=ROOT / 'dataset')
    p.add_argument('--cache', type=Path, default=ROOT / '.cache/ocr')
    p.add_argument('--report', type=Path, default=ROOT / 'evaluation_runs/sample_metrics_coverage_experiment.json')
    args = p.parse_args()
    expected = read_csv(args.dataset / 'sample_output.csv')
    result = {}
    for policy in ['none', 'retained', 'compliant']:
        metrics = compare(run_policy(args.dataset, policy, args.cache), expected)
        result[policy] = {k: metrics[k] for k in
                          ['status_correct', 'status_accuracy', 'whole_case_exact', 'step_precision',
                           'step_recall', 'step_f1', 'content_true_positive', 'content_precision',
                           'content_recall', 'content_f1', 'unmatched_predicted', 'unmatched_expected']}
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(result, indent=2))
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
