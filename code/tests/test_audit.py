"""Independent participant-authored fixtures using the public CSV/JSON/SQL schemas."""
import copy
import csv
import hashlib
import json
from pathlib import Path
import random
import sys
import tempfile
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from ghost_audit.schema import AuditError, read_csv, validate_steps
from ghost_audit.ingest import EvidenceStore
from ghost_audit.engine import Auditor
from ghost_audit.intent import classify

T='2026-06-01T12:00:00Z';OLD='2026-05-01T12:00:00Z';FUTURE='2026-07-01T12:00:00Z'
EMAIL='alice@example.test';USER='user_700001'
FIELDS={
 'user_identities.csv':['user_id','name','email','phone','email_hash','updated_at'],
 'user_audit_log.csv':['audit_id','user_id','event_time','field_name','old_value','new_value'],
 'system_activity.csv':['activity_id','event_time','event_type','source_system','target_system','resource_id','reported_result','details'],
 'evidence_files.csv':['file_id','file_path','origin','captured_at'],
 'deletion_requests.csv':['case_id','email','requested_at','reported_status','reported_at','audit_at','request_text'],
 'deletion_rules.csv':['rule_id','data_category','condition','required_action'],
}

def identity(uid=USER,email=EMAIL):
    return dict(user_id=uid,name='Fictional Test Subject',email=email,phone='+1 202 555 0100',email_hash=hashlib.sha256(email.encode()).hexdigest(),updated_at=OLD)

def record(res='account_812300',cat='USER_PROFILE',state='NOT_FOUND',subject=EMAIL,system='account_service'):
    return dict(recorded_at=T,system=system,resource_id=res,record_type=cat,result=state,subject_reference=subject)

def fixture(root,records=None,extra=None):
    root.mkdir(exist_ok=True);(root/'evidence').mkdir(exist_ok=True)
    request=dict(case_id='case_900001',email=EMAIL,requested_at=OLD,reported_status='COMPLETE',reported_at=OLD,audit_at=T,request_text='Please delete my account.')
    rules=[]
    for cat,action in [('USER_PROFILE','DELETE'),('SEARCH_INDEX_ENTRY','DELETE'),('SUPPORT_MESSAGE','REDACT'),('SUPPORT_ATTACHMENT','DELETE'),('ANALYTICS_PROFILE','ANONYMIZE'),('SECURITY_AUDIT_LOG','RETAIN'),('LEGAL_HOLD_RECORD','RETAIN'),('BACKUP_ARCHIVE','RETAIN'),('ACCOUNT_TOMBSTONE','REDACT'),('USER_EXPORT','DELETE')]:
        rules.append(dict(rule_id='rule_'+str(len(rules)+1),data_category=cat,condition='Synthetic policy fixture',required_action=action))
    data={'user_identities.csv':[identity()],'user_audit_log.csv':[],'system_activity.csv':[], 'deletion_requests.csv':[request],'deletion_rules.csv':rules,'evidence_files.csv':[dict(file_id='evidence_900001',file_path='evidence/observations.json',origin='synthetic_readbacks',captured_at=T)]}
    if extra:data.update(extra)
    for name,rows in data.items():
        with (root/name).open('w',newline='') as f:w=csv.DictWriter(f,fieldnames=FIELDS[name]);w.writeheader();w.writerows(rows)
    (root/'evidence/observations.json').write_text(json.dumps({'exported_at':T,'records':records if records is not None else [record()]}))
    return data,request

def audit(root,request=None):
    s=EvidenceStore(root,images=False)
    a=Auditor(s,read_csv(root/'user_identities.csv'),read_csv(root/'user_audit_log.csv'),read_csv(root/'deletion_rules.csv'))
    return a.investigate(request or read_csv(root/'deletion_requests.csv')[0])

class AuditTests(unittest.TestCase):
    def setUp(self):self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)
    def tearDown(self):self.temp.cleanup()

    def test_historical_identity_and_weak_decoy(self):
        old='former@example.test'
        extra={'user_identities.csv':[identity(),identity('user_700002','decoy@example.test')], 'user_audit_log.csv':[dict(audit_id='audit_900001',user_id=USER,event_time=OLD,field_name='email',old_value=old,new_value=EMAIL)]}
        fixture(self.root,[record(subject=old),record('search_900001','SEARCH_INDEX_ENTRY','FOUND','decoy@example.test','search_service')],extra)
        status,steps,_=audit(self.root);self.assertEqual(status,'COMPLETE');self.assertEqual(len(steps),1)

    def test_multilingual_and_negated_intents(self):
        for text in ['Please do not delete my account.','No elimines mi cuenta.','Ne supprimez pas mon compte.','Please remove me from marketing lists only. I still want receipts for this account.','Could you export a copy of my account data?']:
            self.assertFalse(classify(text).authorized,text)
        for text in ['Solicito la eliminación de mi cuenta.','Je demande la suppression de mon compte.','アカウントの削除を依頼します。','계정 삭제를 요청합니다.','Export my records, then delete my account.']:
            self.assertTrue(classify(text).authorized,text)

    def test_conditional_authorization_requires_proof(self):
        with self.assertRaises(AuditError):classify('If my subscription has expired, delete my account.')
        self.assertTrue(classify('Please delete my account. Contact me if you need information.').authorized)

    def test_export_prerequisite(self):
        _,q=fixture(self.root);q['request_text']='Export my records, then delete my account.'
        with self.assertRaisesRegex(AuditError,'prerequisite'):audit(self.root,q)
        fixture(self.root,[record(),record('export_900001','USER_EXPORT','FOUND',EMAIL,'export_service')])
        self.assertEqual(audit(self.root,q)[0],'INCOMPLETE')

    def test_future_capture_ignored(self):
        data,q=fixture(self.root)
        baseline=audit(self.root)[:2]
        data['evidence_files.csv'].append(dict(file_id='evidence_future',file_path='evidence/future.json',origin='synthetic_readbacks',captured_at=FUTURE))
        fixture(self.root,extra=data)
        (self.root/'evidence/future.json').write_text(json.dumps({'exported_at':FUTURE,'records':[record(state='FOUND')]}))
        self.assertEqual(audit(self.root)[:2],baseline)

    def test_future_event_ignored(self):
        r=record(state='FOUND');r['recorded_at']=FUTURE
        fixture(self.root,[record(),r]);self.assertEqual(audit(self.root)[0],'COMPLETE')

    def test_claimed_success_and_replica(self):
        data,q=fixture(self.root,[record(state='FOUND')]);q['reported_status']='COMPLETE'
        status,steps,_=audit(self.root,q);self.assertEqual(status,'INCOMPLETE');self.assertEqual(steps[0]['operation'],'REPORT_REMAINING_RECORD')
        q['reported_status']='NOT_STARTED';self.assertEqual(audit(self.root,q)[:2],(status,steps))

    def test_primary_absence_does_not_hide_replica(self):
        fixture(self.root,[record()])
        from ghost_audit.schema import Observation
        s=EvidenceStore(self.root,images=False)
        o=copy.deepcopy(s.observations[0]);o.state='PRESENT';o.scope='failover_replica';o.observed_at=OLD
        s.observations.append(o);s.by_resource[o.resource].append(o)
        a=Auditor(s,read_csv(self.root/'user_identities.csv'),[],read_csv(self.root/'deletion_rules.csv'))
        self.assertEqual(a.investigate(read_csv(self.root/'deletion_requests.csv')[0])[0],'INCOMPLETE')

    def test_clean_primary_active_recreation(self):
        fixture(self.root,[record(),record('data_flow_900001','DATA_FLOW','ACTIVE',EMAIL,'integration_service')])
        status,steps,_=audit(self.root);self.assertEqual(status,'INCOMPLETE')
        self.assertEqual([s['operation'] for s in steps],['REPORT_ACTIVE_DATA_FLOW','DISABLE_DATA_FLOW','VERIFY_RECORD_ABSENT','VERIFY_DATA_FLOW_DISABLED'])

    def test_security_retention_and_legal_hold(self):
        fixture(self.root,[record(),record('audit_record_900001','SECURITY_AUDIT_LOG','FOUND',USER,'security_service'),record('legal_hold_900001','LEGAL_HOLD_RECORD','FOUND',USER,'legal_service')])
        status,steps,_=audit(self.root);self.assertEqual(status,'COMPLETE');self.assertEqual(sum(s['operation']=='VERIFY_RECORD_PRESENT' for s in steps),2)

    def test_tombstone_stable_reference_allowed(self):
        data,q=fixture(self.root)
        path=self.root/'evidence/observations.json'
        for name,expected in [(None,'COMPLETE'),('Alice','INCOMPLETE')]:
            path.write_text(json.dumps({'exported_at':T,'snapshots':[{'captured_at':T,'data_store':'account_service','collection':'operational_record_history','records':[record()]},{'captured_at':T,'data_store':'identity_service','collection':'deleted_customer_references','records':[dict(resource_id='tombstone_900001',subject_reference=USER,name=name,email=None,phone=None,email_hash=None,account_status='DELETED')]}]}))
            status,steps,_=audit(self.root);self.assertEqual(status,expected)
            self.assertFalse(any(s['operation']=='DELETE_RECORD' for s in steps))

    def test_backup_active_and_blocked(self):
        for state,want in [('ACTIVE','INCOMPLETE'),('BLOCKED','COMPLETE')]:
            fixture(self.root,[record(),record('backup_900001','BACKUP_ARCHIVE',state,USER,'backup_service')])
            status,steps,_=audit(self.root);self.assertEqual(status,want)
            self.assertFalse(any(s['operation']=='DELETE_RECORD' for s in steps))

    def test_shuffle_and_unrelated_decoy_invariance(self):
        records=[record(),record('search_900002','SEARCH_INDEX_ENTRY','FOUND','other@example.test','search_service')]
        fixture(self.root,records);expected=audit(self.root)[:2]
        random.Random(19).shuffle(records);fixture(self.root,records);self.assertEqual(audit(self.root)[:2],expected)

    def test_evidence_path_rename_invariance(self):
        data,q=fixture(self.root);expected=audit(self.root)[:2]
        (self.root/'evidence/observations.json').rename(self.root/'evidence/arbitrary.json')
        data['evidence_files.csv'][0]['file_path']='evidence/arbitrary.json'
        fixture(self.root,extra=data);self.assertEqual(audit(self.root)[:2],expected)

    def test_no_inference_from_missing_rows(self):
        fixture(self.root,[])
        with self.assertRaisesRegex(AuditError,'no grounded resources'):audit(self.root)

    def test_missing_identity_not_guessed_from_id(self):
        fixture(self.root,[record(subject='no direct identifier')])
        with self.assertRaisesRegex(AuditError,'no grounded resources'):audit(self.root)

    def test_malicious_sql_attach_blocked(self):
        data,q=fixture(self.root)
        data['evidence_files.csv']=[dict(file_id='evidence_bad',file_path='evidence/unsafe.sql',origin='test',captured_at=T)]
        fixture(self.root,extra=data);(self.root/'evidence/unsafe.sql').write_text("ATTACH DATABASE '/tmp/should-not-exist-audit.sqlite' AS outside;")
        with self.assertRaisesRegex(AuditError,'Unsafe/invalid SQL'):audit(self.root)

    def test_manifest_path_traversal_blocked(self):
        data,q=fixture(self.root);data['evidence_files.csv'][0]['file_path']='../outside.json';fixture(self.root,extra=data)
        with self.assertRaisesRegex(AuditError,'escapes'):audit(self.root)

    def test_catalog_identity_conflict_is_not_ignored(self):
        data,q=fixture(self.root,[record(subject='someone_else@example.test',state='FOUND')])
        data['system_activity.csv']=[dict(activity_id='activity_900001',event_time=T,event_type='LINK_RESOURCE_IDENTITY',source_system='data_catalog',target_system='account_service',resource_id='account_812300',reported_result='SUCCESS',details='Linked account_812300 to alice@example.test')]
        fixture(self.root,[record(subject='someone_else@example.test',state='FOUND')],data)
        with self.assertRaisesRegex(AuditError,'ownership conflicts'):audit(self.root)

    def test_hypothetical_request_does_not_authorize(self):
        self.assertFalse(classify('What would happen if I deleted my account?').authorized)
        self.assertFalse(classify('How do I delete my account?').authorized)

    def test_unknown_format_fails(self):
        fixture(self.root);(self.root/'evidence/observations.json').write_text('{"unknown":[]}')
        with self.assertRaisesRegex(AuditError,'Unknown JSON'):audit(self.root)

    def test_phase_and_citation_constraints(self):
        fixture(self.root,[record(state='FOUND')]);status,steps,_=audit(self.root)
        validate_steps(status,steps)
        changed=copy.deepcopy(steps);changed[1]['evidence_id']='evidence_900001'
        with self.assertRaises(AuditError):validate_steps(status,changed)

if __name__=='__main__':unittest.main()
