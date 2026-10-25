#!/usr/bin/env python3
"""Review only unresolved fallback rows with openai/gpt-oss-20b; resumable."""
import argparse
from collections import Counter
import csv
import hashlib
import json
import math
from pathlib import Path
import sys
import time

from main import ROOT, load_environment
from ghost_audit.provenance import behavior_digest
from ghost_audit.schema import AuditError, HEADER, read_csv
from ghost_audit.ingest import EvidenceStore
from ghost_audit.engine import Auditor
from ghost_audit.groq_refiner import (
    MODEL, MAX_OUTPUT_TOKENS, INPUT_USD_PER_MILLION, OUTPUT_USD_PER_MILLION,
    ProviderError, packet_for, request_body, fingerprint, call_groq, usage_of,
    validate_proposal)


def save_json(path, value):
    path.parent.mkdir(parents=True,exist_ok=True)
    temp=path.with_suffix('.tmp');temp.write_text(json.dumps(value,ensure_ascii=False,indent=2));temp.replace(path)


def write_csv(path,rows):
    temp=path.with_suffix('.tmp')
    with temp.open('w',encoding='utf-8',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=HEADER);writer.writeheader();writer.writerows(rows)
    temp.replace(path)


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def dataset_digest(root):
    dataset=(root/'dataset').resolve()
    paths=[dataset/name for name in ['deletion_requests.csv','user_identities.csv','user_audit_log.csv','deletion_rules.csv','system_activity.csv','evidence_files.csv']]
    for m in read_csv(dataset/'evidence_files.csv'):
        path=(dataset/m['file_path']).resolve()
        if not path.is_relative_to(dataset/'evidence'):raise AuditError('Evidence path escapes dataset')
        paths.append(path)
    return hashlib.sha256(json.dumps([(str(p.relative_to(dataset)),sha(p)) for p in sorted(paths)]).encode()).hexdigest()


def totals(entries):
    fields=['input_tokens','cached_input_tokens','output_tokens','total_tokens','estimated_cost_usd']
    return {key:sum(e.get('usage',{}).get(key,0) for e in entries) for key in fields}


def refresh_reports(root, ledger, report):
    entries=ledger['entries'];usage=totals(entries)
    success=sum('usage' in e for e in entries)
    attempted=sum(e.get('api_attempted',False) for e in entries)
    accepted=sum(e['outcome']=='accepted' for e in entries)
    not_attempted=len(set(ledger['target_ids'])-{e['case_id'] for e in entries})
    completed=len({e['case_id'] for e in entries if e['outcome'] in {'accepted','rejected'}})
    insufficient=sum(e.get('proposal',{}).get('resolved') is False for e in entries)
    targets=len(ledger['target_ids'])
    mark=f'\n## Groq refinement of the {targets} fallback cases\n'
    evaluation=root/'code/evaluation/evaluation_report.md'
    text=evaluation.read_text().split('\n## OpenAI refinement of the 104 fallback cases\n')[0].split(mark)[0]
    text+=mark+f'''
Only the {targets} fallback cases are eligible for hosted
review. The other {len(ledger['baseline_rows'])-targets} rows are
preserved exactly. Model: `{MODEL}`. API attempts: {attempted}; responses with
reported token usage: {success}; accepted replacements: {accepted}; remaining
empty fallbacks: {report['fallback_count']}; cases not yet attempted: {not_attempted}.
Cases with completed model responses: {completed}/{targets}. The model explicitly
reported insufficient evidence (`resolved=false`) in {insufficient} responses.
All {len(ledger['baseline_rows'])} case IDs remain unique and lexically sorted. Full step-contract resolution:
{len(ledger['baseline_rows'])-report['fallback_count']}/{len(ledger['baseline_rows'])}; submission ready: **{str(report['fallback_count']==0).lower()}**.
An empty INCOMPLETE fallback is a documented unresolved result, not a valid
evidence-backed remediation plan. Successful API transport does not resolve
missing evidence.

Proposals are checked for intent/status consistency, consecutive numbering,
allowed operations/states, eligible citations, subject ownership, latest replica
state, account coverage, retention policy, and complete remediation/verification
coverage. Unsupported proposals are not inserted to make arrays nonempty.
These are structural/grounding checks, not hidden-label accuracy measurements.

No API calls are made for the 32 public sample cases, because the user restricted
Groq to the {targets} evaluation fallbacks. The sample metrics above measure the local
baseline; no hosted-model sample accuracy or hidden accuracy is claimed.

| Case | Outcome | Detail |
|---|---|---|
'''
    for e in entries:
        detail=e.get('validation_error',e.get('provider_error',e.get('reason','')))
        text+=f"| {e['case_id']} | {e['outcome']} | {str(detail).replace('|','/').replace(chr(10),' ')[:400]} |\n"
    evaluation.write_text(text)
    usage_path=root/'code/evaluation/usage_report.md'
    baseline=ledger['baseline_diagnostics']
    usage_path.write_text(f'''# Usage report — final output and Groq refinement

`output.csv` contains {len(ledger['baseline_rows'])} rows; {accepted} fallback rows
were replaced by validated model proposals, and {report['fallback_count']} empty
fallbacks remain. Output SHA-256: `{sha(root/'output.csv')}`.
Only the {targets} unresolved evaluation cases may be sent to the API.
This report covers the Groq run layered on the local baseline. Earlier OpenAI
experiments had two HTTP 429 failures, no returned usage and no output changes;
the Gemini and Groq credential smoke tests are separate development checks and
are excluded from final-run totals. Failed historical billing is unknown.
The key is loaded locally with python-dotenv and is never stored in reports,
request caches, output, Git, or code.zip.

| Provider/model | API attempts | Responses with usage | Input tokens | Cached input | Output tokens | Total tokens | Estimated known cost |
|---|---:|---:|---:|---:|---:|---:|---:|
| Groq / {MODEL} | {attempted} | {success} | {usage['input_tokens']} | {usage['cached_input_tokens']} | {usage['output_tokens']} | {usage['total_tokens']} | ${usage['estimated_cost_usd']:.6f} |
| Overall hosted totals | {attempted} | {success} | {usage['input_tokens']} | {usage['cached_input_tokens']} | {usage['output_tokens']} | {usage['total_tokens']} | ${usage['estimated_cost_usd']:.6f} |

Across all {len(ledger['baseline_rows'])} output requests: {usage['total_tokens']/len(ledger['baseline_rows']):.3f} reported tokens
and ${usage['estimated_cost_usd']/len(ledger['baseline_rows']):.8f} known estimated API cost per request.
Across the {targets} targeted cases: {usage['total_tokens']/targets:.3f} reported tokens and
${usage['estimated_cost_usd']/targets:.8f} known estimated cost per targeted case.
Calls that fail or are interrupted without usage cannot be assigned invented
token counts or billed costs; {attempted-success} attempt(s) have no usage record.
Recorded totals above exclude unknown usage and are not a billing reconciliation.

Published rates per million tokens: input $0.075, cached input $0.037, output $0.30.
These are list-price estimates; free-tier billing may differ.
Source: [official Groq model documentation](https://console.groq.com/docs/model/openai/gpt-oss-20b),
checked 2026-10-24. The runtime uses only the requested `openai/gpt-oss-20b` alias;
returned model identifiers are recorded per response in the local ledger.
Run cap: ${ledger['max_cost_usd']:.2f}; max response tokens: {MAX_OUTPUT_TOKENS}.
Temporary 429 rate limits are retried up to five times using Retry-After
(maximum 120 seconds per wait); every attempt is logged. Other failures require
explicit retry. Completed responses are cached and never resent.

The preceding local full run used {baseline.get('ocr_calls',0)} RapidOCR image
invocations and {baseline.get('ocr_cache_hits',0)} OCR cache hits, producing
{baseline.get('observations',0)} observations from {baseline.get('evidence_files',0)} files.
The refinement's additional OCR invocations/cache hits are
{ledger.get('ocr_calls',0)}/{ledger.get('ocr_cache_hits',0)}. Local OCR has no API
token billing; CPU/electricity costs are not estimated. Models remain
PP-OCRv6_det_small.onnx, PP-OCRv6_rec_small.onnx and
ch_ppocr_mobile_v2.0_cls_mobile.onnx. Coding-assistant usage is separate and unknown.

Baseline diagnostics, immutable target IDs, per-case prompt hashes, API response
metadata, usage and rejection reasons are in evaluation_runs/groq_refinement/.
These local caches are excluded from code.zip.
''')


def refine(root=ROOT,max_cost_usd=1.0,retry_provider_errors=False):
    if not math.isfinite(max_cost_usd) or max_cost_usd<=0:raise AuditError('Budget must be positive and finite')
    load_environment(root)
    output=root/'output.csv';diag=root/'evaluation_runs/final_run.json'
    directory=root/'evaluation_runs/groq_refinement';journal=directory/'ledger.json'
    directory.mkdir(parents=True,exist_ok=True)
    if journal.exists():
        ledger=json.loads(journal.read_text())
        if ledger.get('behavior_sha256')!=behavior_digest():raise AuditError('Refinement cache predates current evidence/prompt/schema/behavior; do not replay obsolete proposals')
        if ledger['model']!=MODEL:raise AuditError('Cached run uses a different model')
        if sha(output)!=ledger['output_sha256']:raise AuditError('Output changed outside this refinement; refusing to overwrite')
    else:
        rows=read_csv(output);diagnostics=json.loads(diag.read_text())
        target_ids=sorted(d['case_id'] for d in diagnostics['cases'] if d.get('fallback'))
        requested_ids={r['case_id'] for r in read_csv(root/'dataset/deletion_requests.csv')}
        if len(rows)!=518 or {r['case_id'] for r in rows}!=requested_ids:raise AuditError('Baseline must contain exactly the 518 evaluation cases')
        if not target_ids or len(target_ids)!=len(set(target_ids)):raise AuditError('Baseline diagnostics contain no unique unresolved fallback cases')
        if {e['case_id'] for e in diagnostics.get('errors',[])}!=set(target_ids):
            raise AuditError('Fallback diagnostics and error list disagree')
        by_id={r['case_id']:r for r in rows}
        if any(by_id[c]['deletion_status']!='INCOMPLETE' or json.loads(by_id[c]['steps_json'])!=[] for c in target_ids):
            raise AuditError('Target is not an empty INCOMPLETE fallback')
        ledger={'behavior_sha256':behavior_digest(),'model':MODEL,'target_ids':target_ids,'baseline_rows':rows,'baseline_diagnostics':diagnostics,
                'entries':[],'output_sha256':sha(output),'max_cost_usd':max_cost_usd}
        save_json(journal,ledger)
    ledger['max_cost_usd']=max_cost_usd
    if retry_provider_errors:ledger.pop('stop_reason',None)
    digest=dataset_digest(root)
    if ledger.get('dataset_sha256',digest)!=digest:raise AuditError('Participant evidence changed; refusing stale response reuse')
    ledger['dataset_sha256']=digest
    save_json(journal,ledger)
    store=EvidenceStore(root/'dataset',root/'.cache/ocr')
    engine=Auditor(store,read_csv(root/'dataset/user_identities.csv'),read_csv(root/'dataset/user_audit_log.csv'),read_csv(root/'dataset/deletion_rules.csv'))
    ledger['ocr_calls']=ledger.get('ocr_calls',0)+store.ocr_calls
    ledger['ocr_cache_hits']=ledger.get('ocr_cache_hits',0)+store.ocr_cache_hits
    requests={r['case_id']:r for r in read_csv(root/'dataset/deletion_requests.csv')}
    issues={d['case_id']:d['reason'] for d in ledger['baseline_diagnostics']['cases'] if d.get('fallback')}
    previous={e['case_id']:e for e in ledger['entries']}
    blocked=any(e['outcome'] in {'pending','provider_error'} for e in previous.values())
    for cid in ledger['target_ids']:
        if blocked and not retry_provider_errors:
            ledger['stop_reason']='Previous provider failure or interrupted call; explicit --retry-provider-errors required';break
        if cid in previous:
            if previous[cid]['outcome']!='provider_error' or not retry_provider_errors:continue
        packet,observations=packet_for(engine,requests[cid],issues[cid])
        body=request_body(packet)
        # UTF-8 bytes are a conservative input-token bound, plus protocol overhead.
        upper=(len(json.dumps(body,ensure_ascii=False).encode())+1024)*INPUT_USD_PER_MILLION/1e6+MAX_OUTPUT_TOKENS*OUTPUT_USD_PER_MILLION/1e6
        spent_or_reserved=sum(e.get('usage',{}).get('estimated_cost_usd',e.get('reserved_upper_cost_usd',0)) for e in ledger['entries'])
        if spent_or_reserved+upper>max_cost_usd:
            ledger['stop_reason']='Budget cap reached before next call';break
        response=None
        for retry in range(6):
            reserved=sum(e.get('usage',{}).get('estimated_cost_usd',e.get('reserved_upper_cost_usd',0)) for e in ledger['entries'])
            if reserved+upper>max_cost_usd:
                ledger['stop_reason']='Budget cap reached before retry';break
            entry={'case_id':cid,'outcome':'pending','api_attempted':True,'prompt_sha256':fingerprint(body),'requested_model':MODEL,'reserved_upper_cost_usd':upper}
            ledger['entries'].append(entry);save_json(directory/(cid+'_request.json'),body);save_json(journal,ledger)
            start=time.perf_counter()
            try:
                response=call_groq(body)
                break
            except ProviderError as e:
                entry.update(outcome='provider_error',provider_error=str(e))
                save_json(journal,ledger)
                if e.retry_after is not None and retry<5 and e.retry_after<=120:
                    print(f'{cid}: temporary rate limit; waiting {e.retry_after:.1f}s',flush=True)
                    time.sleep(e.retry_after+1)
                    continue
                ledger['stop_reason']=str(e);print(str(e),flush=True);break
        if response is None:
            if 'json_validate_failed' in ledger.get('stop_reason',''):
                ledger.pop('stop_reason',None)
                print(f'{cid}: structured generation failed; preserving fallback and continuing',flush=True)
                continue
            break
        save_json(directory/(cid+'_response.json'),response)
        entry['response_model']=response.get('model');entry['response_id']=response.get('id')
        entry['elapsed_seconds']=round(time.perf_counter()-start,3)
        try:
            entry['usage']=usage_of(response)
            choice=response['choices'][0]
            if choice['finish_reason']!='stop' or choice['message'].get('refusal'):raise AuditError('Model refused or output was truncated')
            proposal=json.loads(choice['message']['content'])
            entry['proposal']=proposal
            status,steps,detail=validate_proposal(proposal,engine,requests[cid],observations)
            entry.update(outcome='accepted',replacement={'case_id':cid,'deletion_status':status,'steps_json':json.dumps(steps,ensure_ascii=False,separators=(',',':'))},diagnostic=detail)
        except (AuditError,KeyError,TypeError,ValueError) as e:
            entry.update(outcome='rejected',validation_error=str(e))
        save_json(journal,ledger)
        print(f"{len({e['case_id'] for e in ledger['entries'] if e['outcome'] in {'accepted','rejected'}})}/{len(ledger['target_ids'])} {cid}: {entry['outcome']}; known cost ${totals(ledger['entries'])['estimated_cost_usd']:.5f}",flush=True)
    replacements={e['case_id']:e for e in ledger['entries'] if e['outcome']=='accepted'}
    final_rows=[replacements[r['case_id']]['replacement'] if r['case_id'] in replacements else r for r in ledger['baseline_rows']]
    # Assert the requested blast radius, including all 10 legitimate [] non-deletion rows.
    assert all(a==b for a,b in zip(final_rows,ledger['baseline_rows']) if b['case_id'] not in ledger['target_ids'])
    report=json.loads(json.dumps(ledger['baseline_diagnostics']))
    report['cases']=[replacements[d['case_id']]['diagnostic'] if d['case_id'] in replacements else d for d in report['cases']]
    report['errors']=[e for e in report['errors'] if e['case_id'] not in replacements]
    report['fallback_count']=len(ledger['target_ids'])-len(replacements)
    report['status_distribution']=dict(Counter(r['deletion_status'] for r in final_rows))
    report['operations']=dict(Counter(s['operation'] for r in final_rows for s in json.loads(r['steps_json'])))
    usage=totals(ledger['entries']);report.update(usage)
    report['llm_calls']=sum(e.get('api_attempted',False) for e in ledger['entries'])
    report['api_cost_usd']=usage['estimated_cost_usd'];report.pop('openai_model',None);report['groq_model']=MODEL
    write_csv(output,final_rows);save_json(diag,report)
    ledger['output_sha256']=sha(output);save_json(journal,ledger)
    refresh_reports(root,ledger,report)
    return {'targets':len(ledger['target_ids']),'api_attempts':report['llm_calls'],'accepted':len(replacements),'remaining_fallbacks':report['fallback_count'],**usage,'stop_reason':ledger.get('stop_reason')}


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--max-cost-usd',type=float,required=True,help='Explicit approved API budget required; no default paid run')
    p.add_argument('--retry-provider-errors',action='store_true',help='Explicitly retry failed requests after correcting access/quota; completed responses are never repeated')
    a=p.parse_args()
    result=refine(max_cost_usd=a.max_cost_usd,retry_provider_errors=a.retry_provider_errors);print(json.dumps(result,indent=2))
    return 0 if not result['remaining_fallbacks'] else 2


if __name__=='__main__':sys.exit(main())
