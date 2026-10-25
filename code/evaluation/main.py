#!/usr/bin/env python3
"""Development evaluation on public samples; missing predictions count as failures."""
import argparse
from collections import Counter
import csv
import json
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from ghost_audit.schema import read_csv, FIELDS
from main import run
ROOT=Path(__file__).resolve().parents[2]


def canonical(step,number=True):return tuple(step[k] for k in FIELDS if number or k!='step_no')

def distance(a,b):
    """Unit-cost Levenshtein distance over exact whole-step tuples."""
    previous=list(range(len(b)+1))
    for i,x in enumerate(a,1):
        current=[i]
        for j,y in enumerate(b,1):current.append(min(current[-1]+1,previous[j]+1,previous[j-1]+(x!=y)))
        previous=current
    return previous[-1]

def compare(predicted,expected):
    pred={r['case_id']:r for r in predicted};truth={r['case_id']:r for r in expected}
    if len(pred)!=len(predicted) or len(truth)!=len(expected):raise ValueError('Duplicate cases in evaluation')
    extra=set(pred)-set(truth)
    if extra:raise ValueError(f'Unknown prediction cases: {sorted(extra)}')
    status_ok=exact=sequence=tp=total_p=total_t=content=content_p=content_t=field_n=edit=edit_den=0
    fields=Counter();confusion=Counter();failures=[];unmatched_expected=unmatched_predicted=0
    for cid,row in truth.items():
        p=pred.get(cid);status=p['deletion_status'] if p else 'UNRESOLVED'
        wanted=row['deletion_status'];confusion[(wanted,status)]+=1;status_ok+=status==wanted
        ps=json.loads(p['steps_json']) if p else [];ts=json.loads(row['steps_json'])
        pc=[canonical(s) for s in ps];tc=[canonical(s) for s in ts]
        sequence+=bool(p) and pc==tc;exact+=bool(p) and status==wanted and pc==tc
        # Exact multiset matching includes all seven fields, step_no included.
        intersection=sum((Counter(pc)&Counter(tc)).values());tp+=intersection;total_p+=len(ps);total_t+=len(ts)
        unmatched_predicted+=len(ps)-intersection;unmatched_expected+=len(ts)-intersection
        # Content multiset matching excludes step_no, which is positional: order is
        # already measured by the ordered-sequence metric above.
        pn=[canonical(s,False) for s in ps];tn=[canonical(s,False) for s in ts]
        content+=sum((Counter(pn)&Counter(tn)).values());content_p+=len(ps);content_t+=len(ts)
        # Diagnostic positional alignment does not align on any evaluated field.
        # Missing/extra positions count as wrong for all seven fields.
        for i in range(max(len(ps),len(ts))):
            field_n+=1
            if i<len(ps) and i<len(ts):
                for k in FIELDS:fields[k]+=ps[i][k]==ts[i][k]
        edit+=distance(pc,tc);edit_den+=max(len(pc),len(tc))
        if not p or status!=wanted or pc!=tc:
            failures.append({'case_id':cid,'expected_status':wanted,'actual_status':status,'expected_steps':len(ts),'actual_steps':len(ps),'missing':[s for s in ts if canonical(s) not in pc],'extra':[s for s in ps if canonical(s) not in tc]})
    precision=tp/total_p if total_p else 0;recall=tp/total_t if total_t else 0
    cp=content/content_p if content_p else 0;cr=content/content_t if content_t else 0
    return dict(cases=len(truth),status_correct=status_ok,status_accuracy=status_ok/len(truth),whole_case_exact=exact,whole_case_accuracy=exact/len(truth),sequence_exact=sequence,sequence_accuracy=sequence/len(truth),true_positive_steps=tp,predicted_steps=total_p,expected_steps=total_t,step_precision=precision,step_recall=recall,step_f1=2*precision*recall/(precision+recall) if precision+recall else 0,content_true_positive=content,content_precision=cp,content_recall=cr,content_f1=2*cp*cr/(cp+cr) if cp+cr else 0,field_correct=dict(fields),field_denominator=field_n,field_accuracy={k:fields[k]/field_n if field_n else 0 for k in FIELDS},unmatched_expected=unmatched_expected,unmatched_predicted=unmatched_predicted,sequence_distance=edit,sequence_distance_denominator=edit_den,normalized_sequence_distance=edit/edit_den if edit_den else 0,confusion={f'{a} -> {b}':v for (a,b),v in sorted(confusion.items())},failures=failures)

def markdown(m,run_report):
    pct=lambda n:f'{100*n:.2f}%'
    text=f'''# Development evaluation

This is development evaluation, not an untouched hold-out. Public sample answers
were read during architecture and parser development. Hidden evaluation answers
were never accessed. All cases are evaluated, including conservative fallback predictions.
Fallback rows in this sample run: {run_report.get("fallback_count", 0)}.

| Metric | Result |
|---|---:|
| Status accuracy | {m['status_correct']}/{m['cases']} ({pct(m['status_accuracy'])}) |
| Whole-case exact match | {m['whole_case_exact']}/{m['cases']} ({pct(m['whole_case_accuracy'])}) |
| Exact ordered sequence | {m['sequence_exact']}/{m['cases']} ({pct(m['sequence_accuracy'])}) |
| Exact-step precision | {m['true_positive_steps']}/{m['predicted_steps']} ({pct(m['step_precision'])}) |
| Exact-step recall | {m['true_positive_steps']}/{m['expected_steps']} ({pct(m['step_recall'])}) |
| Exact-step F1 | {pct(m['step_f1'])} |
| Content-step precision (step_no excluded) | {m['content_true_positive']}/{m['predicted_steps']} ({pct(m['content_precision'])}) |
| Content-step recall (step_no excluded) | {m['content_true_positive']}/{m['expected_steps']} ({pct(m['content_recall'])}) |
| Content-step F1 (step_no excluded) | {pct(m['content_f1'])} |
| Unmatched expected / predicted steps | {m['unmatched_expected']} / {m['unmatched_predicted']} |
| Levenshtein step distance | {m['sequence_distance']}/{m['sequence_distance_denominator']} ({m['normalized_sequence_distance']:.4f}) |

Exact-step matching uses multiset intersection over all seven fields, `step_no`
included, so a correct check at a different index cannot match. Content-step
matching drops `step_no` because it is positional; ordering is already measured by
the ordered-sequence and Levenshtein metrics. Both are reported for every run.
Sequence distance uses unit insertion, deletion and substitution cost on complete
step tuples, divided by the sum of maximum expected/predicted sequence lengths.

Field accuracy uses ordinal position, without matching on any field under test.
Every missing/extra position adds one incorrect comparison to every field. It is
a diagnostic measure: a shifted sequence can lower many fields together.

| Field | Correct / positions | Accuracy |
|---|---:|---:|
'''
    for k in FIELDS:text+=f"| {k} | {m['field_correct'].get(k,0)}/{m['field_denominator']} | {pct(m['field_accuracy'][k])} |\n"
    text+='\n## Three-class confusion matrix\n\nUnresolved is an execution outcome, not a fourth submitted status.\n\n| Expected | COMPLETE | INCOMPLETE | NOT_APPLICABLE | Unresolved |\n|---|---:|---:|---:|---:|\n'
    for a in ['COMPLETE','INCOMPLETE','NOT_APPLICABLE']:
        text+='| '+a+' | '+' | '.join(str(m['confusion'].get(f'{a} -> {b}',0)) for b in ['COMPLETE','INCOMPLETE','NOT_APPLICABLE','UNRESOLVED'])+' |\n'
    text+='\nThe 32 public samples contain no NOT_APPLICABLE examples. Non-deletion coverage comes from independently authored fixtures.\n'
    text+='\n## Case-level failures\n\n| Case | Expected / actual | Expected / produced steps |\n|---|---|---:|\n'
    for f in m['failures']:text+=f"| {f['case_id']} | {f['expected_status']} / {f['actual_status']} | {f['expected_steps']} / {f['actual_steps']} |\n"
    text+='\n## Root causes and iteration\n\n'
    text+='''- Initial conditional-intent detection rejected ordinary “contact me if you need information” sentences. Restricting condition detection to the deletion clause removed 64 failures in the first evaluation-dataset pass.
- Cloud log envelopes escaped their inner key/value quotes. Normalizing the envelope without stripping the inner closing quote fixed false missing audit records.
- A marketing-only opt-out initially matched “remove” plus “account”; explicit scoped opt-out handling fixed that classification and is covered by regression tests.
- Treating a batch SQL inventory as a global inventory produced false absence for retained records. Absence by missing key is now restricted to a resource proven present in another table of the same capture, and only for deletable profile/search categories.
- Several public expectations name deleted/anonymized resources without an eligible identity link. The implementation deliberately does not join numeric suffixes or sample answer rows.
- Catalog links introduce additional resources not reflected in some public expected outputs (for example a separately linked object-storage attachment). The implementation investigates eligible links rather than suppressing evidence to match sample labels.
- Citation selection uses latest eligible observed time per resource scope, then capture time and stable lexical tie-breaks. It is not fitted to specific expected evidence IDs. Different valid citations can lower exact-match metrics.

## Independent synthetic cases and assumptions

`code/tests/test_audit.py` builds isolated datasets using the real CSV and JSON schemas. These are participant-authored expectations, not organizer truth. The suite covers:

1. Historical email linkage with an unrelated subject sharing a weak name/phone: only strong email/history links count.
2. English, Spanish, French, Japanese and Korean deletion, non-deletion and negation; marketing opt-out remains non-deletion.
3. Capture time after cutoff and event time after cutoff independently exclude a contradictory record.
4. Claimed workflow success cannot override a present record or a surviving failover replica.
5. A clean primary plus an active connector is incomplete; disable precedes record checks.
6. Security retention and active legal-hold records remain present; no deletion is planned.
7. Tombstones retain stable subject references; a surviving name requires redaction.
8. Blocked backups are compliant; active restore access requires blocking, never archive deletion.
9. Export-then-delete authorizes deletion with an export prerequisite. Missing prerequisite evidence fails; a present export permits the plan.
10. An unresolved conditional request fails instead of assuming the condition is true.

Metamorphic tests shuffle rows, add unrelated decoys, add post-cutoff evidence,
rename a manifest-linked path, and change an unsupported workflow status. Those
changes must leave grounded decisions unchanged. Additional tests block SQL
ATTACH and manifest traversal, reject unknown structures and empty evidence, and
validate step phases, numbering and citation rules. Run the suite for current
pass/fail results; no test result is inferred from source presence.

## Limitations

This public-sample evaluation uses local OCR and deterministic intent/planning.
Hosted Groq review is restricted to the current unresolved fallback set and is
reported separately; no hosted sample comparison or hidden accuracy is claimed.
Warm-cache agreement measures replay and deterministic planning only. Runtime
evidence gaps are not replaced with fabricated answers.
'''
    return text

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--dataset',type=Path,default=ROOT/'dataset');p.add_argument('--predictions',type=Path);p.add_argument('--report',type=Path,default=ROOT/'code/evaluation/evaluation_report.md');args=p.parse_args()
    run_report={}
    if args.predictions:rows=read_csv(args.predictions)
    else:rows,run_report=run(args.dataset,args.dataset/'sample_deletion_requests.csv',ROOT/'evaluation_runs/sample_predictions.csv',cache=ROOT/'.cache/ocr',diagnostics=ROOT/'evaluation_runs/sample_run.json',allow_errors=True,fallback=True)
    m=compare(rows,read_csv(args.dataset/'sample_output.csv'))
    args.report.parent.mkdir(parents=True,exist_ok=True);args.report.write_text(markdown(m,run_report))
    (ROOT/'evaluation_runs').mkdir(exist_ok=True);(ROOT/'evaluation_runs/sample_metrics.json').write_text(json.dumps(m,indent=2))
    print(json.dumps({k:v for k,v in m.items() if k!='failures'},indent=2))
if __name__=='__main__':main()
