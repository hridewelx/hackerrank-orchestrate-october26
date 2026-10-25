#!/usr/bin/env python3
"""Refresh final-run reports; token totals come from saved provider responses only."""
import hashlib
import json
from pathlib import Path
import re
import sys
from collections import Counter
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from main import ROOT
from ghost_audit.schema import read_csv
from ghost_audit.intent import classify
from ghost_audit.groq_refiner import MODEL, usage_of

MARK='\n## Identity and intent repair verification\n'

def language(text):
    for name,pattern in [('es',r'Solicito la|Borra'),('pt',r'Solicito a|apague'),('fr',r'Je demande|Effacez'),('ja',r'削除|消去'),('ko',r'삭제')]:
        if re.search(pattern,text,re.I):return name
    return None

def main():
    report=json.loads((ROOT/'evaluation_runs/final_run.json').read_text())
    sample=json.loads((ROOT/'evaluation_runs/sample_metrics.json').read_text())
    sample_run=json.loads((ROOT/'evaluation_runs/sample_run.json').read_text())
    before_path=ROOT/'evaluation_runs/identity_fix/before/sample_metrics.json'
    before=json.loads(before_path.read_text()) if before_path.exists() else None
    output=read_csv(ROOT/'output.csv');requests={r['case_id']:r for r in read_csv(ROOT/'dataset/deletion_requests.csv')}
    digest=hashlib.sha256((ROOT/'output.csv').read_bytes()).hexdigest()
    path=ROOT/'code/evaluation/evaluation_report.md'
    text=path.read_text().split(MARK)[0]+MARK
    text+='\nThe sample evaluator was run before pipeline edits. The requested diagnostic was initially absent; its failed invocation was saved. After the participant supplied it, the script was saved unchanged and run against the untouched baseline before identity/intent edits. This is development evaluation, not hidden-label accuracy.\n\n'
    text+='| Metric | Before | After |\n|---|---:|---:|\n'
    for label,key in [('Status accuracy','status_accuracy'),('Step precision','step_precision'),('Step recall','step_recall'),('Step F1','step_f1'),('Whole-case exact match','whole_case_accuracy'),('Sequence exact match','sequence_accuracy')]:
        old=f'{before[key]*100:.2f}%' if before else 'Historical snapshot unavailable'
        text+=f'| {label} | {old} | {sample[key]*100:.2f}% |\n'
    unchanged=before is not None and all(before[k]==sample[k] for k in ['status_accuracy','step_precision','step_recall','step_f1','whole_case_accuracy'])
    text+=('\nMeasured sample metrics are unchanged. ' if unchanged else '\nSee the measured comparison above; no improvement is assumed. ')
    text+='The request-email trim defect and identity-time gate were real robustness bugs, but the existing unresolved cases already resolved to a subject. The current dataset has no relevant identity changes beyond the cutoff. Full user history is now indexed by user_id; raw emails, hashes and phones are retained, while only normalized emails, hashes and stable user IDs establish ownership. Late email changes warn separately and cannot block completion; evidence timestamps still control state.\n\n'
    text+='Added regression coverage: historical request email; uppercase/whitespace normalization without source mutation; multi-hop email/hash/phone expansion; ambiguous ownership; late identity changes with eligible and future evidence. Expanded Spanish, Portuguese, French, Japanese and Korean deletion/negation cases.\n\n'
    text+='### Final output and degraded cases\n\n'
    text+=f"{len(output)} sorted unique rows. Status distribution: `{json.dumps(report['status_distribution'],sort_keys=True)}`. **{report['fallback_count']} unresolved INCOMPLETE statuses are fallback guesses**, with `steps_json=[]`, not evidence-backed findings. Every case is listed in root `degraded_cases.md`. No dummy steps or IDs were introduced. Full semantic submission readiness remains false while these cases are unresolved.\n\n"
    reasons=Counter(e['error'] for e in report['errors'])
    text+='| Unresolved root cause | Count |\n|---|---:|\n'
    for reason,count in reasons.items():text+=f"| {reason.replace('|','/')} | {count} |\n"
    text+='\n### Supplied diagnostic, before and after\n\nThe supplied checker reports formatting/ordering problems separately from empty arrays. Zero contract problems therefore does not establish semantic completeness. The following outputs preserve its bucket definitions.\n'
    for label,name in [('Before','before/diagnose_provided.stdout.txt'),('After','after_diagnose.stdout.txt')]:
        p=ROOT/'evaluation_runs/identity_fix'/name
        if p.exists():
            diagnostic=p.read_text().split('NOT_APPLICABLE rows')[0].rstrip()
            text+=f'\n{label}:\n\n```text\n{diagnostic}\n```\n'
    text+='\n### Non-deletion intent review\n\n| Case | Verdict | Steps | Request |\n|---|---|---|---|\n'
    for row in output:
        if row['deletion_status']=='NOT_APPLICABLE':
            request=requests[row['case_id']]
            assert not classify(request['request_text']).authorized and json.loads(row['steps_json'])==[]
            text+=f"| {row['case_id']} | NOT_APPLICABLE | [] | {request['request_text'].replace('|','/')} |\n"
    counts=Counter()
    for row in output:
        request=requests[row['case_id']];lang=language(request['request_text'])
        if lang:
            assert classify(request['request_text']).authorized and row['deletion_status']!='NOT_APPLICABLE'
            counts[lang]+=1
    text+=f'\nNon-English deletion requests checked by their request text: `{json.dumps(dict(counts),sort_keys=True)}`; none was NOT_APPLICABLE. Unresolved multilingual cases remain deletion-authorized fallbacks.\n'
    text+=f"\n### Fresh versus cached processing\n\nThe final full-dataset run used `code/main.py --no-cache`: {report['ocr_calls']} fresh OCR invocations, {report['ocr_cache_hits']} cache hits, {report['observations']} observations, {report['elapsed_seconds']:.3f} seconds. The separate sample evaluation used {sample_run['ocr_calls']} fresh OCR invocations and {sample_run['ocr_cache_hits']} cache hits. Hosted calls in the final full run: {report['llm_calls']}; prior Groq responses were not replayed to change predictions. Output SHA-256: `{digest}`.\n"
    path.write_text(text,encoding='utf-8')

    # Historical token/cost measurements are recomputed from original responses,
    # never copied from an estimated ledger or inferred from prompt length.
    response_dir=ROOT/'evaluation_runs/groq_refinement'
    actual=[]
    for p in sorted(response_dir.glob('*_response.json')):
        response=json.loads(p.read_text())
        if response.get('model')!=MODEL:raise ValueError(f'Unpriced response model in {p.name}')
        actual.append(usage_of(response))
    fields=['input_tokens','cached_input_tokens','output_tokens','total_tokens','estimated_cost_usd']
    totals={k:sum(u[k] for u in actual) for k in fields}
    ledger_path=response_dir/'ledger.json'
    ledger=json.loads(ledger_path.read_text()) if ledger_path.exists() else None
    attempts=sum(e.get('api_attempted',False) for e in ledger['entries']) if ledger else 0
    targets=len(ledger['target_ids']) if ledger else 0
    assert report['llm_calls']==0,'This report generator requires a final local run; hosted final runs use their response-linked report'
    usage=f'''# Usage report — actual final run and historical API responses

The final 518-case output was generated cold with `code/main.py --no-cache`.
Output SHA-256: `{digest}`. The final run made **0 hosted API calls**, consumed
0 cached hosted responses and generated 0 hosted tokens; estimated hosted cost
is $0. No provider usage is inferred from local prompt lengths or code execution.
No previously rejected Groq proposal was reused to fill output rows.

| Final-run provider/model | Calls | Input tokens | Output tokens | Total tokens | Estimated cost |
|---|---:|---:|---:|---:|---:|
| Hosted overall (none) | 0 | 0 | 0 | 0 | $0 |

Final hosted averages across 518 requests: 0 input/output/total tokens and $0 per request.
Local RapidOCR models: PP-OCRv6_det_small.onnx, PP-OCRv6_rec_small.onnx,
ch_ppocr_mobile_v2.0_cls_mobile.onnx. Full run: {report['ocr_calls']} fresh image
invocations, {report['ocr_cache_hits']} OCR cache hits. Separate sample evaluation:
{sample_run['ocr_calls']} fresh invocations, {sample_run['ocr_cache_hits']} cache hits.
Local inference has no provider token bill; electricity/hardware and coding-agent
usage are not measured. The run extracted {report['observations']} observations
from {report['evidence_files']} evidence files.

## Earlier Groq experiment (separate from the final cold run)

Recomputed directly from {len(actual)} original `*_response.json` files in the local
Groq run directory. These are historical measurements, not new calls or cache hits
in the final run. The journal records {attempts} attempts; {max(0,attempts-len(actual))}
attempts have no response usage and their tokens/billing remain unknown.

| Provider/model | Responses with usage | Input (includes cached) | Cached input | Output | Total | Known estimated cost |
|---|---:|---:|---:|---:|---:|---:|
| Groq / {MODEL} | {len(actual)} | {totals['input_tokens']} | {totals['cached_input_tokens']} | {totals['output_tokens']} | {totals['total_tokens']} | ${totals['estimated_cost_usd']:.9f} |
| Historical overall | {len(actual)} | {totals['input_tokens']} | {totals['cached_input_tokens']} | {totals['output_tokens']} | {totals['total_tokens']} | ${totals['estimated_cost_usd']:.9f} |

Historical reported averages per {targets} targeted requests: {totals['total_tokens']/targets:.3f}
total tokens and ${totals['estimated_cost_usd']/targets:.9f}. Across the 518-request
dataset: {totals['total_tokens']/518:.3f} tokens and ${totals['estimated_cost_usd']/518:.9f}.
Earlier OpenAI/Gemini credential or failed-generation experiments are not part of
the final run; absent usage responses are not assigned invented token counts.

Pricing: $0.075 per million uncached input tokens, $0.037 cached input, $0.30 output.
Source: [Groq GPT OSS 20B documentation](https://console.groq.com/docs/model/openai/gpt-oss-20b),
verified **2026-10-25**. Cost = ((input-cached)*0.075 + cached*0.037 + output*0.30)/1,000,000.
These are list-price estimates, not a bill; free-tier treatment and unmetered
failures are excluded. Raw responses, request caches and credentials are excluded
from code.zip. No key is included in this report.
'''
    (ROOT/'code/evaluation/usage_report.md').write_text(usage,encoding='utf-8')
    print(json.dumps({'full_rows':len(output),'degraded':report['fallback_count'],'non_english_deletion_counts':dict(counts),'historical_groq_usage_from_responses':totals},indent=2))

if __name__=='__main__':main()
