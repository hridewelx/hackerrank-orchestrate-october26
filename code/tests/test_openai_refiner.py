"""Offline regression tests: no real provider calls or credentials."""
import copy
import json
import io
import os
import urllib.error
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from test_audit import fixture, record, T, FUTURE, audit
from ghost_audit.schema import AuditError, read_csv
from ghost_audit.ingest import EvidenceStore
from ghost_audit.engine import Auditor
from ghost_audit.openai_refiner import (
    MODEL, packet_for, request_body, validate_proposal, call_openai, ProviderError, usage_of)
from refine_openai import refine


class OpenAIRefinerTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)
        _,self.request=fixture(self.root)
        self.refresh()

    def tearDown(self):self.temp.cleanup()

    def refresh(self):
        store=EvidenceStore(self.root,images=False)
        self.engine=Auditor(store,read_csv(self.root/'user_identities.csv'),read_csv(self.root/'user_audit_log.csv'),read_csv(self.root/'deletion_rules.csv'))

    def proposal(self, status='COMPLETE'):
        status,steps,_=audit(self.root)
        return dict(authorized=True,intent_reason='Deletion request',resolved=True,reason='Eligible readbacks',deletion_status=status,steps_json=steps)

    def test_model_is_fixed_and_request_is_structured(self):
        packet,_=packet_for(self.engine,self.request,'test')
        body=request_body(packet)
        self.assertEqual(body['model'],'gpt-4o-mini')
        self.assertTrue(body['response_format']['json_schema']['strict'])
        self.assertFalse(body['store'])
        self.assertNotIn('OPENAI_API_KEY',json.dumps(body))
        with self.assertRaises(AuditError):call_openai({'model':'other-model'})

    def test_future_observations_and_activities_are_not_sent(self):
        future=record('account_999999',state='FOUND');future['recorded_at']=FUTURE
        data,_=fixture(self.root,[record(),future])
        data['system_activity.csv']=[dict(activity_id='activity_future',event_time=FUTURE,event_type='DELETE_RECORD',source_system='account_service',target_system='account_service',resource_id='account_812300',reported_result='SUCCESS',details='alice@example.test')]
        fixture(self.root,[record(),future],data);self.refresh()
        packet,_=packet_for(self.engine,self.request,'test')
        self.assertNotIn('account_999999',json.dumps(packet))
        self.assertNotIn('activity_future',json.dumps(packet))

    def test_consecutive_numbering_normalizes_model_numbers(self):
        p=self.proposal();p['steps_json'][0]['step_no']=9
        _,obs=packet_for(self.engine,self.request,'test')
        _,steps,_=validate_proposal(p,self.engine,self.request,obs)
        self.assertEqual([s['step_no'] for s in steps],list(range(1,len(steps)+1)))

    def test_invented_resource_or_citation_rejected(self):
        _,obs=packet_for(self.engine,self.request,'test')
        for field,value in [('resource_id','account_999999'),('evidence_id','evidence_missing')]:
            p=self.proposal();p['steps_json'][0][field]=value
            with self.assertRaises(AuditError):validate_proposal(p,self.engine,self.request,obs)

    def test_no_completion_without_account_coverage(self):
        fixture(self.root,[record('search_812300','SEARCH_INDEX_ENTRY','NOT_FOUND',system='search_service')]);self.refresh()
        _,obs=packet_for(self.engine,self.request,'test')
        p=dict(authorized=True,intent_reason='Delete',resolved=True,reason='Clean search',deletion_status='COMPLETE',steps_json=[dict(step_no=1,phase='VERIFICATION',system_id='search_service',resource_id='search_812300',operation='VERIFY_RECORD_ABSENT',state='ABSENT',evidence_id='evidence_900001')])
        with self.assertRaisesRegex(AuditError,'coverage'):validate_proposal(p,self.engine,self.request,obs)

    def test_incomplete_plan_requires_matching_policy_and_all_checks(self):
        fixture(self.root,[record(state='FOUND')]);self.refresh();p=self.proposal()
        _,obs=packet_for(self.engine,self.request,'test')
        self.assertEqual(validate_proposal(copy.deepcopy(p),self.engine,self.request,obs)[0],'INCOMPLETE')
        p['steps_json']=[s for s in p['steps_json'] if s['phase']!='REMEDIATION']
        with self.assertRaises(AuditError):validate_proposal(p,self.engine,self.request,obs)

    def test_model_admits_insufficient_evidence(self):
        p=self.proposal();p['resolved']=False;p['reason']='Missing identity link'
        with self.assertRaisesRegex(AuditError,'Missing identity link'):validate_proposal(p,self.engine,self.request,[])

    def test_usage_counts_cached_tokens_without_double_counting(self):
        u=usage_of({'usage':dict(prompt_tokens=1000,completion_tokens=100,total_tokens=1100,prompt_tokens_details={'cached_tokens':400})})
        self.assertEqual(u['total_tokens'],1100)
        self.assertAlmostEqual(u['estimated_cost_usd'],.00018)

    def test_quota_error_never_exposes_raw_key_message(self):
        raw=json.dumps({'error':{'code':'insufficient_quota','message':'secret-test-key should never be printed'}}).encode()
        error=urllib.error.HTTPError('https://api.openai.com',429,'Too many requests',{},io.BytesIO(raw))
        with patch.dict(os.environ,{'OPENAI_API_KEY':'secret-test-key'}):
            with patch('urllib.request.build_opener') as opener:
                opener.return_value.open.side_effect=error
                with self.assertRaises(ProviderError) as caught:call_openai({'model':MODEL})
        self.assertIn('insufficient_quota',str(caught.exception))
        self.assertNotIn('secret-test-key',str(caught.exception))

    def test_not_applicable_remains_empty(self):
        p=dict(authorized=False,intent_reason='Access only',resolved=True,reason='No deletion',deletion_status='NOT_APPLICABLE',steps_json=[])
        status,steps,_=validate_proposal(p,self.engine,self.request,[])
        self.assertEqual((status,steps),('NOT_APPLICABLE',[]))

    def test_only_104_targets_called_and_remaining_rows_preserved(self):
        root=self.root/'project';data=root/'dataset';data.mkdir(parents=True)
        _,q=fixture(data)
        ids=[f'case_{i:04}' for i in range(518)];rows=[];details=[];requests=[]
        for i,cid in enumerate(ids):
            requests.append(dict(q,case_id=cid))
            rows.append(dict(case_id=cid,deletion_status='INCOMPLETE' if i<104 else 'NOT_APPLICABLE',steps_json='[]'))
            details.append(dict(case_id=cid,fallback=i<104,reason='test missing link',resources=[]))
        import csv
        for path,records in [(data/'deletion_requests.csv',requests),(root/'output.csv',rows)]:
            with path.open('w',newline='') as f:
                w=csv.DictWriter(f,fieldnames=list(records[0]));w.writeheader();w.writerows(records)
        (root/'evaluation_runs').mkdir()
        (root/'evaluation_runs/final_run.json').write_text(json.dumps({'cases':details,'errors':[{'case_id':cid,'error':'test'} for cid in ids[:104]],'fallback_count':104}))
        (root/'code/evaluation').mkdir(parents=True)
        (root/'code/evaluation/evaluation_report.md').write_text('Baseline evaluation\n')
        answer=dict(authorized=True,intent_reason='Delete',resolved=False,reason='Missing proof',deletion_status='INCOMPLETE',steps_json=[])
        response={'id':'offline-test','model':MODEL,'usage':{'prompt_tokens':10,'completion_tokens':10,'total_tokens':20},'choices':[{'finish_reason':'stop','message':{'content':json.dumps(answer)}}]}
        with patch('refine_openai.call_openai',return_value=response) as mock:
            with patch('builtins.print'):
                result=refine(root)
                refine(root)
            self.assertEqual(mock.call_count,104)
            called=[json.loads(c.args[0]['messages'][1]['content'])['request']['case_id'] for c in mock.call_args_list]
            self.assertEqual(called,ids[:104])
        self.assertEqual(result['remaining_fallbacks'],104)
        self.assertEqual(read_csv(root/'output.csv'),rows)


if __name__=='__main__':unittest.main()
