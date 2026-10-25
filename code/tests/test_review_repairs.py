"""Independent review regressions, synthetic participant-facing fixtures only."""
import copy,csv,hashlib,json,subprocess,sys,tempfile,unittest
from pathlib import Path
from test_audit import fixture,record,audit,identity,T,OLD,FUTURE,EMAIL,USER
from ghost_audit.ingest import EvidenceStore
from ghost_audit.intent import classify
from ghost_audit.schema import AuditError, read_csv, timestamp
from main import run
from validate import validate

class ReviewRepairs(unittest.TestCase):
    def setUp(self):self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)
    def tearDown(self):self.tmp.cleanup()
    def test_scoped_authorization(self):
        for text in ["Please don't remove my account.","I am not requesting deletion of my account.","I am not asking you to erase my profile.","Please do not remove my personal records.","No quiero eliminar mi cuenta.","Não quero apagar minha conta.","Je ne demande pas la suppression de mon compte."]:
            with self.subTest(text=text):self.assertFalse(classify(text).authorized)
        for text in ["Delete my account, but do not delete the invoices you must retain.","Erase my profile; keep the legally required audit records.","Supprimez mon compte, mais ne supprimez pas les factures obligatoires.","Elimina mi cuenta, pero no borres las facturas legales.","Exclua minha conta, mas não apague as faturas obrigatórias."]:
            with self.subTest(text=text):self.assertTrue(classify(text).authorized)
        with self.assertRaises(AuditError):classify('Delete my account, but keep my account active.')
    def test_intent_paraphrases_and_copy_prerequisites(self):
        for text in [
            "I do not want my account deleted.",
            "Why would I delete my account?",
            "Is it possible to delete my account?",
            "Do I need to delete my account?",
            "Please remove me from your mailing list.",
            "Unsubscribe me from marketing emails.",
            "I want to update my email address.",
            "Please correct my personal details.",
            "I request access to my personal data.",
            "Send me the information you hold about me.",
            "Please export a copy of my account data.",
            "My details are out of date; please update them.",
        ]:
            with self.subTest(text=text):self.assertFalse(classify(text).authorized)
        for text in [
            "Please close my account and delete my data.",
            "Delete everything unless you are legally required to retain invoices.",
            "Delete my account, but do not delete the invoices you must retain.",
            "Erase my profile; keep the legally required audit records.",
        ]:
            with self.subTest(text=text):self.assertTrue(classify(text).authorized)
        for text in [
            "Delete my account and send me a confirmation copy.",
            "Please delete my account and email me a copy of the confirmation.",
            "Delete my profile and send a confirmation receipt.",
            "Delete my account. I already downloaded my data.",
            "Delete my account; I don't need a copy.",
        ]:
            with self.subTest(text=text):self.assertEqual(classify(text).prerequisites,())
        for text in ["Export my records, then delete my account.","Download my data first, then close my account."]:
            with self.subTest(text=text):self.assertEqual(classify(text).prerequisites,('export',))
    def test_future_identity_is_invariant(self):
        records=[record(),record('search_999999','SEARCH_INDEX_ENTRY','FOUND','future-alias@example.test','search_service')]
        data,q=fixture(self.root,records);before=audit(self.root)[:2]
        data['user_audit_log.csv']=[dict(audit_id='audit_future',user_id=USER,event_time=FUTURE,field_name='email',old_value=EMAIL,new_value='future-alias@example.test')]
        fixture(self.root,records,data)
        self.assertEqual(audit(self.root)[:2],before)
    def support_fixture(self,content,category='support_conversations'):
        fixture(self.root)
        r={'resource_id':'support_999999','user_id':USER,'name':None,'email':None,'phone':None,**content}
        (self.root/'evidence/observations.json').write_text(json.dumps({'snapshots':[{'captured_at':T,'collection':'customer_profiles','records':[record()]},{'captured_at':T,'collection':category,'records':[r]}]}))
    def test_phone_in_retained_text_requires_redaction(self):
        self.support_fixture({'message_text':'My phone number is +1 202 555 0100. Please call me.'})
        status,steps,_=audit(self.root)
        self.assertEqual(status,'INCOMPLETE')
        self.assertIn('REDACT_RECORD',[s['operation'] for s in steps])
    def test_nested_identifiers_and_redacted_controls(self):
        for content in [{'thread':[{'body':'Call +1 (202) 555-0100'}]}, {'thread':[{'body':'Fictional Test Subject'}]}, {'thread':[{'body':identity()['email_hash']}]}, {'thread':[{'email':EMAIL}]}]:
            with self.subTest(content=content):
                self.support_fixture(content);self.assertEqual(audit(self.root)[0],'INCOMPLETE')
        self.support_fixture({'thread':[{'body':'[redacted]'},'Anonymous customer question']})
        self.assertEqual(audit(self.root)[0],'COMPLETE')
    def test_partial_backup_findings_survive_missing_resource(self):
        data,q=fixture(self.root,[record(),record('backup_900001','BACKUP_ARCHIVE','ACTIVE',USER,'backup_service')])
        data['system_activity.csv']=[dict(activity_id='activity_link',event_time=T,event_type='LINK_RESOURCE_IDENTITY',source_system='catalog',target_system='identity_service',resource_id='tombstone_999999',reported_result='SUCCESS',details='Linked to '+EMAIL)]
        fixture(self.root,[record(),record('backup_900001','BACKUP_ARCHIVE','ACTIVE',USER,'backup_service')],data)
        _,report=run(self.root,self.root/'deletion_requests.csv',self.root/'review.csv',images=False,degraded=True)
        d=report['cases'][0]
        self.assertTrue(d['fallback'])
        self.assertTrue(any(s['operation']=='REPORT_RESTORE_RISK' for s in d.get('partial_steps',[])))
    def test_explicit_deleted_tombstone_proves_account_treatment(self):
        fixture(self.root)
        tombstone=dict(resource_id='tombstone_998877',subject_reference=USER,name=None,email=None,phone=None,email_hash=None,account_status='DELETED')
        path=self.root/'evidence/observations.json'
        path.write_text(json.dumps({'snapshots':[{'captured_at':T,'collection':'deleted_customer_references','records':[tombstone]}]}))
        status,steps,_=audit(self.root)
        self.assertEqual(status,'COMPLETE')
        self.assertEqual([s['operation'] for s in steps],['VERIFY_RECORD_REDACTED'])
        del tombstone['account_status']
        path.write_text(json.dumps({'snapshots':[{'captured_at':T,'collection':'deleted_customer_references','records':[tombstone]}]}))
        with self.assertRaises(AuditError):audit(self.root)

    def test_reused_email_respects_eligible_ownership_intervals(self):
        from ghost_audit.identity import IdentityIndex
        from ghost_audit.schema import timestamp
        shared='shared@example.test';a=identity();b=identity('user_700002',shared)
        a['updated_at']=b['updated_at']='2026-05-11T00:00:00Z'
        history=[dict(audit_id='audit_a',user_id=USER,event_time='2026-05-10T00:00:00Z',field_name='email',old_value=shared,new_value=EMAIL),dict(audit_id='audit_b',user_id=b['user_id'],event_time='2026-05-10T00:00:00Z',field_name='email',old_value='other@example.test',new_value=shared)]
        index=IdentityIndex([a,b],history);cut=timestamp(T)
        self.assertEqual(index.at(shared,cut,OLD)[0],USER)
        self.assertTrue(index.matches(USER,{shared},'2026-05-05T00:00:00Z',cut))
        self.assertFalse(index.matches(USER,{shared},'2026-05-20T00:00:00Z',cut))
        self.assertTrue(index.matches(USER,{USER,shared},'2026-05-20T00:00:00Z',cut))

    def test_future_snapshot_alone_does_not_establish_past_identity(self):
        data,q=fixture(self.root);data['user_identities.csv'][0]['updated_at']=FUTURE
        fixture(self.root,extra=data)
        with self.assertRaisesRegex(AuditError,'eligible identity'):audit(self.root)

    def test_query_metadata_is_not_stored_pii(self):
        self.support_fixture({'lookup_key':EMAIL,'thread':[{'body':'Anonymous question'}]})
        self.assertEqual(audit(self.root)[0],'COMPLETE')

    def test_analytics_stable_reference_requires_anonymization(self):
        self.support_fixture({'thread':[{'body':'Anonymous visit'}]},'customer_analytics_profiles')
        status,steps,_=audit(self.root)
        self.assertEqual(status,'INCOMPLETE');self.assertIn('ANONYMIZE_RECORD',[s['operation'] for s in steps])

    def test_stale_diagnostics_and_future_citations_rejected(self):
        fixture(self.root,[record(state='FOUND')]);out=self.root/'review.csv';diag=self.root/'diagnostics.json'
        rows,report=run(self.root,self.root/'deletion_requests.csv',out,images=False,diagnostics=diag)
        changed=copy.deepcopy(report);changed['cases'][0]['resources'][0]['state']='ABSENT';diag.write_text(json.dumps(changed))
        with self.assertRaises(AuditError):validate(out,self.root,diag)
        diag.write_text(json.dumps(report))
        p=self.root/'evidence/observations.json';data=json.loads(p.read_text());data['records'][0]['recorded_at']=FUTURE;p.write_text(json.dumps(data))
        with self.assertRaisesRegex(AuditError,'mismatched'):validate(out,self.root,diag)
        from ghost_audit.provenance import dataset_digest
        report['bindings']['dataset_sha256']=dataset_digest(self.root);diag.write_text(json.dumps(report))
        with self.assertRaises(AuditError):validate(out,self.root,diag)

    def test_strict_cli_preserves_existing_output(self):
        fixture(self.root,[]);out=self.root/'output.csv';out.write_text('prior artifact\n')
        cli=Path(__file__).resolve().parents[1]/'main.py'
        r=subprocess.run([sys.executable,str(cli),'--strict','--dataset',str(self.root),'--output',str(out),'--diagnostics',str(self.root/'diagnostics.json'),'--no-images'],capture_output=True,text=True)
        self.assertEqual(r.returncode,2)
        self.assertIn('AUDIT FAILED',r.stderr)
        self.assertEqual(out.read_text(),'prior artifact\n')

    def test_documented_default_command_writes_output_with_loud_warning(self):
        # The README documents `code/main.py --no-cache`; that must produce the
        # 518-row answer, warn loudly on stderr and never claim readiness.
        fixture(self.root,[]);out=self.root/'output.csv'
        cli=Path(__file__).resolve().parents[1]/'main.py'
        r=subprocess.run([sys.executable,str(cli),'--dataset',str(self.root),'--output',str(out),'--diagnostics',str(self.root/'diagnostics.json'),'--no-images'],capture_output=True,text=True)
        self.assertEqual(r.returncode,0,r.stderr)
        rows=read_csv(out)
        self.assertEqual([(x['case_id'],x['deletion_status'],x['steps_json']) for x in rows],[('case_900001','INCOMPLETE','[]')])
        self.assertIn('WARNING: DEGRADED OUTPUT',r.stderr)
        self.assertIn('1 of 1 cases could not be resolved',r.stderr)
        self.assertIn('--strict',r.stderr)
        self.assertTrue((self.root/'degraded_cases.md').exists())
    def audit_with(self,policy,records=None,data=None):
        from ghost_audit.ingest import EvidenceStore
        from ghost_audit.engine import Auditor
        if records is not None:fixture(self.root,records,data)
        store=EvidenceStore(self.root,images=False)
        engine=Auditor(store,read_csv(self.root/'user_identities.csv'),read_csv(self.root/'user_audit_log.csv'),read_csv(self.root/'deletion_rules.csv'),coverage_waiver=policy)
        return engine.investigate(read_csv(self.root/'deletion_requests.csv')[0])

    def test_retained_only_exact_key_link_permits_grounded_completion(self):
        records=[record('audit_record_900001','SECURITY_AUDIT_LOG','FOUND',USER,'security_service')]
        status,steps,detail=self.audit_with('retained',records)
        self.assertEqual(status,'COMPLETE')
        self.assertEqual([(s['phase'],s['operation'],s['state'],s['resource_id'],s['evidence_id']) for s in steps],
            [('VERIFICATION','VERIFY_RECORD_PRESENT','PRESENT','audit_record_900001','evidence_900001')])
        self.assertEqual(detail['coverage_waiver'],'retained-records-only')
        with self.assertRaisesRegex(AuditError,'No grounded account resource'):self.audit_with('none')

    def test_waiver_requires_compliant_linked_records(self):
        records=[record('audit_record_900001','SECURITY_AUDIT_LOG','FOUND',USER,'security_service'),
                 record('support_900001','SUPPORT_MESSAGE','FOUND',EMAIL,'support_platform')]
        status,steps,detail=self.audit_with('compliant',records)
        self.assertEqual(status,'INCOMPLETE')
        self.assertIn('REPORT_EXPOSED_PII',[s['operation'] for s in steps])
        self.assertNotIn('coverage_waiver',detail)

    def test_waiver_needs_an_exact_key_not_a_name_or_position(self):
        from ghost_audit.engine import Auditor
        from ghost_audit.schema import Observation
        fixture(self.root)
        engine=Auditor(EvidenceStore(self.root,images=False),read_csv(self.root/'user_identities.csv'),read_csv(self.root/'user_audit_log.csv'),read_csv(self.root/'deletion_rules.csv'))
        def obs(ids):return Observation('e','p',T,T,'s','r','SECURITY_AUDIT_LOG','PRESENT',ids,'loc')
        self.assertTrue(engine.exact_key_grounded(USER,[obs({USER})],timestamp(T)))
        self.assertTrue(engine.exact_key_grounded(USER,[obs({EMAIL})],timestamp(T)))
        self.assertFalse(engine.exact_key_grounded(USER,[obs({'Fictional Test Subject'})],timestamp(T)))
        self.assertFalse(engine.exact_key_grounded(USER,[obs(set())],timestamp(T)))
        self.assertFalse(engine.exact_key_grounded(USER,[obs({USER}),obs(set())],timestamp(T)))

    def test_catalog_claim_yields_to_observed_artifact_content(self):
        data,q=fixture(self.root,[record('marketing_900001','MARKETING_PROFILE','FOUND','other.person@example.test','marketing_platform')])
        data['system_activity.csv']=[dict(activity_id='activity_link',event_time=T,event_type='LINK_RESOURCE_IDENTITY',source_system='data_catalog',target_system='marketing_platform',resource_id='marketing_900001',reported_result='SUCCESS',details=f'Data catalog linked marketing_900001 (marketing_900001) to {EMAIL} and {USER}.')]
        fixture(self.root,[record('marketing_900001','MARKETING_PROFILE','FOUND','other.person@example.test','marketing_platform')],data)
        with self.assertRaisesRegex(AuditError,'no grounded resources') as caught:self.audit_with('compliant')
        overrides=caught.exception.diagnostic['ownership_overrides']
        self.assertEqual([o['resource'] for o in overrides],['marketing_900001'])
        self.assertEqual(overrides[0]['artifact_identifiers'],['other.person@example.test'])

    def test_catalog_claim_kept_when_artifact_content_agrees(self):
        data,q=fixture(self.root,[record('marketing_900001','MARKETING_PROFILE','FOUND',EMAIL,'marketing_platform')])
        data['system_activity.csv']=[dict(activity_id='activity_link',event_time=T,event_type='LINK_RESOURCE_IDENTITY',source_system='data_catalog',target_system='marketing_platform',resource_id='marketing_900001',reported_result='SUCCESS',details=f'Data catalog linked marketing_900001 (marketing_900001) to {EMAIL} and {USER}.')]
        fixture(self.root,[record('marketing_900001','MARKETING_PROFILE','FOUND',EMAIL,'marketing_platform')],data)
        status,steps,detail=self.audit_with('compliant')
        self.assertEqual(detail['ownership_overrides'],[])
        self.assertEqual(status,'INCOMPLETE')
        self.assertIn('marketing_900001',[s['resource_id'] for s in steps])

    def test_degraded_writes_best_effort_without_claiming_readiness(self):
        from unittest.mock import patch
        import main as harness
        fixture(self.root,[])
        with patch.object(harness,'ROOT',self.root):
            rows,report=harness.run(self.root,self.root/'deletion_requests.csv',self.root/'output.csv',images=False,degraded=True)
        self.assertEqual([(r['deletion_status'],r['steps_json']) for r in rows],[('INCOMPLETE','[]')])
        self.assertFalse(report['submission_ready'])
        self.assertTrue(report['degraded'])
        self.assertFalse(report['strict'])
        self.assertEqual(report['fallback_count'],1)
        # The library default stays fail-closed.
        before=(self.root/'output.csv').read_bytes()
        with self.assertRaises(AuditError):harness.run(self.root,self.root/'deletion_requests.csv',self.root/'output.csv',images=False)
        self.assertEqual((self.root/'output.csv').read_bytes(),before)

    def test_reference_only_tombstone_screen_establishes_deleted_account(self):
        from PIL import Image, ImageDraw, ImageFont
        from ghost_audit.ingest import EvidenceStore
        data,q=fixture(self.root)
        png=self.root/'evidence/tombstone.png'
        image=Image.new('RGB',(900,400),'white');draw=ImageDraw.Draw(image)
        font=ImageFont.truetype('/usr/share/fonts/liberation-sans-fonts/LiberationSans-Regular.ttf',48)
        draw.text((250,80),USER,fill='black',font=font)
        draw.text((250,170),'Retained reference',fill='black',font=font)
        image.save(png)
        data['evidence_files.csv']=[dict(file_id='evidence_screen',file_path='evidence/tombstone.png',origin='identity_service',captured_at=T)]
        data['system_activity.csv']=[dict(activity_id='activity_link',event_time=T,event_type='LINK_RESOURCE_IDENTITY',source_system='data_catalog',target_system='identity_service',resource_id='tombstone_900001',reported_result='SUCCESS',details=f'Data catalog linked tombstone_900001 ({USER}) to {EMAIL} and {USER}.')]
        fixture(self.root,extra=data)
        store=EvidenceStore(self.root,images=True)
        tomb=[o for o in store.observations if o.resource=='tombstone_900001']
        self.assertEqual(len(tomb),1)
        self.assertEqual((tomb[0].category,tomb[0].state),('ACCOUNT_TOMBSTONE','REDACTED'))
        self.assertFalse(any(d.get('warning','').startswith('Reference-only') for d in store.diagnostics))

    def test_reference_screen_with_direct_identifier_requires_redaction(self):
        from PIL import Image, ImageDraw, ImageFont
        data,q=fixture(self.root)
        png=self.root/'evidence/tombstone.png'
        image=Image.new('RGB',(900,400),'white');draw=ImageDraw.Draw(image)
        font=ImageFont.truetype('/usr/share/fonts/liberation-sans-fonts/LiberationSans-Regular.ttf',48)
        draw.text((250,80),USER,fill='black',font=font)
        draw.text((250,170),'Retained reference',fill='black',font=font)
        draw.text((250,260),'Fictional Test Subject',fill='black',font=font)
        image.save(png)
        data['evidence_files.csv']=[dict(file_id='evidence_screen',file_path='evidence/tombstone.png',origin='identity_service',captured_at=T)]
        data['system_activity.csv']=[dict(activity_id='activity_link',event_time=T,event_type='LINK_RESOURCE_IDENTITY',source_system='data_catalog',target_system='identity_service',resource_id='tombstone_900001',reported_result='SUCCESS',details=f'Data catalog linked tombstone_900001 ({USER}) to {EMAIL} and {USER}.')]
        fixture(self.root,extra=data)
        from ghost_audit.ingest import EvidenceStore
        from ghost_audit.engine import Auditor
        store=EvidenceStore(self.root,images=True)
        a=Auditor(store,read_csv(self.root/'user_identities.csv'),read_csv(self.root/'user_audit_log.csv'),read_csv(self.root/'deletion_rules.csv'))
        status,steps,_=a.investigate(read_csv(self.root/'deletion_requests.csv')[0])
        self.assertEqual(status,'INCOMPLETE')
        self.assertIn('REDACT_RECORD',[s['operation'] for s in steps])

    def test_backup_inventory_screen_requires_restore_block(self):
        from PIL import Image, ImageDraw, ImageFont
        from ghost_audit.ingest import EvidenceStore
        from ghost_audit.engine import Auditor
        data,q=fixture(self.root)
        png=self.root/'evidence/backup.png'
        image=Image.new('RGB',(1600,900),'white');draw=ImageDraw.Draw(image)
        font=ImageFont.truetype('/usr/share/fonts/liberation-sans-fonts/LiberationSans-Regular.ttf',36)
        draw.text((300,500),'backup_900001',fill='black',font=font)
        draw.text((650,500),EMAIL,fill='black',font=font)
        image.save(png)
        data['evidence_files.csv']=[dict(file_id='evidence_backup',file_path='evidence/backup.png',origin='backup_service',captured_at=T)]
        fixture(self.root,extra=data)
        store=EvidenceStore(self.root,images=True)
        found=[o for o in store.observations if o.resource=='backup_900001']
        self.assertEqual(len(found),1)
        self.assertEqual((found[0].category,found[0].state),('BACKUP_ARCHIVE','ACTIVE'))
        engine=Auditor(store,read_csv(self.root/'user_identities.csv'),read_csv(self.root/'user_audit_log.csv'),read_csv(self.root/'deletion_rules.csv'))
        status,steps,_=engine.investigate(read_csv(self.root/'deletion_requests.csv')[0])
        self.assertEqual(status,'INCOMPLETE')
        self.assertIn('REPORT_RESTORE_RISK',[s['operation'] for s in steps])
        self.assertIn('BLOCK_RESTORE',[s['operation'] for s in steps])

    def test_semantic_mutations_rejected_even_with_rebound_output_hash(self):
        fixture(self.root,[record(state='FOUND')]);out=self.root/'review.csv';diag=self.root/'diagnostics.json'
        rows,report=run(self.root,self.root/'deletion_requests.csv',out,images=False,diagnostics=diag)
        self.assertEqual(validate(out,self.root,diag),1)
        def wrong_policy(steps):
            steps[0]['operation']='REPORT_EXPOSED_PII';steps[1].update(operation='REDACT_RECORD',state='REDACTED');steps[2].update(operation='VERIFY_RECORD_REDACTED',state='REDACTED')
        def wrong_state(steps):steps[0].update(operation='REPORT_RESTORE_RISK',state='ACTIVE')
        def missing_check(steps):steps.pop()
        def unsupported(steps):steps[0]['resource_id']='account_777777'
        def unrelated(steps):steps[0]['evidence_id']='evidence_unrelated'
        def duplicate(steps):steps.append(copy.deepcopy(steps[0]))
        def reorder(steps):steps[1],steps[2]=steps[2],steps[1]
        def wrong_phase(steps):steps[0]['phase']='VERIFICATION'
        def wrong_number(steps):steps[1]['step_no']=99
        def missing_citation(steps):steps[0]['evidence_id']=''
        def remediated_citation(steps):steps[1]['evidence_id']='evidence_900001'
        for name,mutate in [('policy',wrong_policy),('state',wrong_state),('missing check',missing_check),('unsupported',unsupported),('unrelated',unrelated),('authorization',None),('duplicate',duplicate),('reorder',reorder),('phase',wrong_phase),('number',wrong_number),('missing citation',missing_citation),('remediation citation',remediated_citation)]:
            changed=copy.deepcopy(rows);steps=json.loads(changed[0]['steps_json'])
            if mutate:mutate(steps)
            else:changed[0]['deletion_status']='NOT_APPLICABLE';steps=[]
            changed[0]['steps_json']=json.dumps(steps)
            with out.open('w',newline='') as f:
                w=csv.DictWriter(f,fieldnames=list(changed[0]));w.writeheader();w.writerows(changed)
            bound=copy.deepcopy(report)
            if 'bindings' in bound:bound['bindings']['output_sha256']=hashlib.sha256(out.read_bytes()).hexdigest()
            diag.write_text(json.dumps(bound))
            with self.subTest(name=name),self.assertRaises(AuditError):validate(out,self.root,diag)

    def test_recomputed_diagnostics_fields_cannot_be_forged(self):
        fixture(self.root,[record(state='FOUND')]);out=self.root/'review.csv';diag=self.root/'diagnostics.json'
        _,report=run(self.root,self.root/'deletion_requests.csv',out,images=False,diagnostics=diag)
        self.assertEqual(validate(out,self.root,diag),1)
        for field,value in [('subject','user_999999'),('intent',{'authorized':False,'reason':'forged'}),('resources',[]),('fallback',True)]:
            changed=copy.deepcopy(report);changed['cases'][0][field]=value;diag.write_text(json.dumps(changed))
            with self.subTest(field=field),self.assertRaises(AuditError):validate(out,self.root,diag)

if __name__=='__main__':unittest.main()
