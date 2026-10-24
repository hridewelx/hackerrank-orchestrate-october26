"""Parse participant evidence once, retaining source scope, times and locators."""
import hashlib
import json
import re
import sqlite3
import subprocess
from collections import defaultdict
from pathlib import Path
from .schema import AuditError, Observation, Scope, read_csv
from .identity import tokens, RESOURCE

COLLECTIONS={
 'customer_profiles':('account_service','USER_PROFILE'),
 'customer_search_documents':('search_service','SEARCH_INDEX_ENTRY'),
 'search_documents_primary':('search_service','SEARCH_INDEX_ENTRY'),
 'customer_analytics_reports':('analytics_platform','ANALYTICS_PROFILE'),
 'customer_analytics_profiles':('analytics_platform','ANALYTICS_PROFILE'),
 'backup_catalog':('backup_service','BACKUP_ARCHIVE'),
 'backup_restore_entries':('backup_service','BACKUP_ARCHIVE'),
 'customer_export_jobs':('export_service','USER_EXPORT'),
 'customer_exports':('export_service','USER_EXPORT'),
 'connector_configurations':('integration_service','DATA_FLOW'),
 'connector_subscriptions':('integration_service','DATA_FLOW'),
 'security_audit_events':('security_service','SECURITY_AUDIT_LOG'),
 'security_audit_records':('security_service','SECURITY_AUDIT_LOG'),
 'ticket_attachments':('support_platform','SUPPORT_ATTACHMENT'),
 'support_conversations':('support_platform','SUPPORT_MESSAGE'),
 'support_records':('support_platform','SUPPORT_MESSAGE'),
 'retained_order_records':('legal_service','LEGAL_HOLD_RECORD'),
 'deleted_customer_references':('identity_service','ACCOUNT_TOMBSTONE'),
}
SERVICE_COLLECTIONS={'profile_lookups':'customer_profiles','profiles':'customer_analytics_profiles','restore_entries':'backup_restore_entries','exports':'customer_exports','connectors':'connector_subscriptions','index_queries':'customer_search_documents','audit_records':'security_audit_records','tickets':'support_records'}
DIRECT_KEYS={'name','full_name','display_name','email','phone','email_hash','requester_name','requester_email','requester_phone','owner_email','owner_phone','customer_email'}
NULLS={'','null','none','[redacted]','redacted','no direct identifier'}

def has_pii(record, stable=False):
    for k,v in record.items():
        if isinstance(v,dict) and has_pii(v,stable): return True
        if k in DIRECT_KEYS and v is not None and str(v).casefold() not in NULLS:return True
        if k in {'message_text','message_excerpt'} and any('@' in x for x in tokens(v)):return True
        if stable and k in {'user_id','customer_reference','subject_reference'} and v:return True
    return False

def truth(v):return str(v).lower() in {'true','1','yes'}

def physical_state(category,r):
    if category=='USER_PROFILE' and 'profile' in r:return 'ABSENT' if r['profile'] is None and r.get('status_code')==404 else 'PRESENT'
    if category=='SEARCH_INDEX_ENTRY' and 'hits' in r:return 'PRESENT' if r['hits']['total'] else 'ABSENT'
    if category=='DATA_FLOW':return 'ACTIVE' if truth(r['enabled']) else 'DISABLED'
    if category=='BACKUP_ARCHIVE':return 'ACTIVE' if truth(r['restore_allowed']) else 'BLOCKED'
    if category in {'ANALYTICS_PROFILE','PRODUCT_TELEMETRY'}:return 'IDENTIFIABLE' if has_pii(r,True) else 'ANONYMIZED'
    if category in {'SUPPORT_MESSAGE','ACCOUNT_TOMBSTONE','EMAIL_DELIVERY_LOG'}:return 'IDENTIFIABLE' if has_pii(r) else 'REDACTED'
    return 'PRESENT'

class EvidenceStore:
    def __init__(self, dataset, cache=None, no_cache=False, images=True):
        self.dataset=Path(dataset).resolve();self.cache=Path(cache) if cache else None
        self.no_cache=no_cache;self.images=images
        self.observations=[];self.scopes=[];self.links=[];self.diagnostics=[];self.ocr_calls=0;self.ocr_cache_hits=0
        self.ocr_engine=None
        self.manifest=read_csv(self.dataset/'evidence_files.csv')
        self.activities=read_csv(self.dataset/'system_activity.csv')
        for m in self.manifest:
            p=(self.dataset/m['file_path']).resolve()
            if not p.is_relative_to(self.dataset/'evidence'):raise AuditError('Manifest path escapes evidence directory')
            if p.suffix=='.sql':self.sql(m,p)
            elif p.suffix=='.json':self.json(m,p)
            elif p.suffix in {'.log','.txt'}:self.lines(m,p)
            elif p.suffix=='.pdf':self.document(m,p)
            elif p.suffix=='.png':
                if images:self.screenshot(m,p)
                else:self.diagnostics.append({'file':m['file_id'],'warning':'Images disabled; ablation only'})
            else:raise AuditError(f'Unsupported evidence format: {p.suffix}')
        for a in self.activities:
            ids=tokens(a['details'])
            if ids:self.links.append((a['event_time'],a['event_time'],a['resource_id'],ids,a['activity_id']))
        self.by_identifier=defaultdict(list);self.by_resource=defaultdict(list)
        for o in self.observations:
            self.by_resource[o.resource].append(o)
            for ident in o.identifiers:self.by_identifier[ident].append(o)

    def add(self,m,time,system,resource,category,state,data,locator,scope='service',limitations=''):
        if not resource or not system or not category:raise AuditError(f'Missing observation identity in {m["file_id"]} at {locator}: {system}/{resource}/{category}')
        state={'FOUND':'PRESENT','NOT_FOUND':'ABSENT'}.get(state,state)
        o=Observation(m['file_id'],m['file_path'],m['captured_at'],time,system,resource,category,state,tokens(data),locator,data,scope,True,limitations)
        self.observations.append(o)
        return o

    def record(self,m,r,time,collection,locator,scope='service'):
        if 'record_type' in r:
            self.add(m,r.get('recorded_at',time),r['system'],r['resource_id'],r['record_type'],r['result'],r,locator,scope)
            return
        if collection not in COLLECTIONS:raise AuditError(f'Unknown collection {collection}')
        sys,cat=COLLECTIONS[collection]
        self.add(m,r.get('observed_at',time),sys,r['resource_id'],cat,physical_state(cat,r),r,locator,scope)

    def json(self,m,p):
        d=json.loads(p.read_text())
        if 'snapshots' in d:
            for n,s in enumerate(d['snapshots']):
                for i,r in enumerate(s['records']):self.record(m,r,s['captured_at'],s['collection'],f'snapshots[{n}].records[{i}]')
                # A bundle does not declare complete coverage. Never infer absence from omission.
        elif 'service_exports' in d:
            for system,groups in d['service_exports'].items():
                for group,records in groups.items():
                    for i,r in enumerate(records):self.record(m,r,r['observed_at'],SERVICE_COLLECTIONS[group],f'service_exports.{system}.{group}[{i}]')
        elif 'records' in d:
            for i,r in enumerate(d['records']):self.record(m,r,d.get('captured_at',d.get('exported_at')),d.get('collection',''),f'records[{i}]')
        else:raise AuditError(f'Unknown JSON structure in {m["file_id"]}')

    def sql(self,m,p):
        db=sqlite3.connect(':memory:');db.row_factory=sqlite3.Row
        # Explicitly deny attachment, extension loading, arbitrary pragmas, deletes,
        # virtual tables and triggers. The input is data, never executable authority.
        allowed={sqlite3.SQLITE_CREATE_TABLE,sqlite3.SQLITE_CREATE_INDEX,sqlite3.SQLITE_INSERT,sqlite3.SQLITE_UPDATE,sqlite3.SQLITE_READ,sqlite3.SQLITE_SELECT,sqlite3.SQLITE_TRANSACTION,sqlite3.SQLITE_FUNCTION,sqlite3.SQLITE_REINDEX}
        def authorizer(action,a,b,dbname,source):
            if action==sqlite3.SQLITE_PRAGMA:return sqlite3.SQLITE_OK if a=='foreign_keys' else sqlite3.SQLITE_DENY
            if action==sqlite3.SQLITE_FUNCTION:return sqlite3.SQLITE_OK if b in {'json_valid'} else sqlite3.SQLITE_DENY
            if action==sqlite3.SQLITE_UPDATE and a!='sqlite_master':return sqlite3.SQLITE_DENY
            return sqlite3.SQLITE_OK if action in allowed else sqlite3.SQLITE_DENY
        db.set_authorizer(authorizer)
        try:
            db.executescript(p.read_text())
            tables=[r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")]
            for table in tables:
                if not re.fullmatch('[A-Za-z_0-9]+',table):raise AuditError('Unsafe table name')
                rows=[dict(r) for r in db.execute(f'SELECT * FROM "{table}"')]
                if table=='snapshot_scope':continue
                if table.startswith('customer_data_'):
                    for i,r in enumerate(rows):self.record(m,json.loads(r['record_json']),m['captured_at'],r['collection_name'],f'{table}[{i}]',table)
                else:
                    collection='customer_profiles' if table.startswith('customer_profiles_') else table
                    if collection not in COLLECTIONS:raise AuditError(f'Unknown SQL table {table}')
                    sys,cat=COLLECTIONS[collection]
                    for i,r in enumerate(rows):self.record(m,r,m['captured_at'],collection,f'{table}[{i}]',table)
                    self.scopes.append(Scope(m['file_id'],m['file_path'],m['captured_at'],m['captured_at'],sys,cat,{r['resource_id'] for r in rows},table,table))
        except sqlite3.Error as e:raise AuditError(f'Unsafe/invalid SQL in {m["file_id"]}: {e}') from e
        finally:db.close()

    def lines(self,m,p):
        traces={}
        for i,line in enumerate(p.read_text().splitlines(),1):
            loc=f'line {i}'
            if line.startswith('- ') and ' | ' in line:
                parts=line[2:].split(' | ')
                if len(parts)==6:
                    time,sys,res,cat,state,subject=parts
                    self.add(m,time,sys,res,cat,state,{'subject_reference':subject},loc)
                continue
            line=line.replace('\\"','"')
            if ' message="' in line:line=line.replace(' message="',' ',1).rstrip('"')
            kv={k:(a if a is not None and a!='' else b) for k,a,b in re.findall(r'(\w+)=(?:"([^"]*)"|([^\s]+))',line)}
            if line[21:].startswith('{'):kv=json.loads(line[21:])
            time=line[:20]
            if not re.match(r'\d{4}-\d\d-\d\dT',time):continue
            brackets=re.match(r'\S+ \[\w+\] \[([^]]+)\] \[([^]]+)\] (\w+):',line)
            sys=kv.get('service','');trace=kv.get('trace_id','');event=kv.get('event','')
            if brackets:sys,trace,event=brackets.groups()
            syslog=re.match(r'\S+ <\d+>1 \S+ (\S+) (\S+) - -',line)
            if syslog:sys,trace=syslog.groups()
            if ' | ' in line:
                parts=line.split(' | ',5)
                if len(parts)==6:sys,trace,event=parts[2:5]
            sys=kv.get('function',sys);trace=kv.get('requestId',trace)
            if trace:
                old=traces.get(trace,{})
                # Use only earlier lines within this trace; never future context.
                kv={**old,**kv};traces[trace]=kv.copy()
            res=kv.get('resource_id')
            if not res:continue
            if 'record_type' in kv:
                self.add(m,time,kv['system'],res,kv['record_type'],kv['result'],kv,loc);continue
            state=cat=None
            if event=='profile_lookup_completed':cat='USER_PROFILE';state='ABSENT' if kv.get('rows')=='0' and kv.get('http_status')=='404' else 'PRESENT'
            elif event=='index_query_completed':cat='SEARCH_INDEX_ENTRY';state='PRESENT' if kv.get('result')=='hit' else 'ABSENT'
            elif event in {'message_pii_scan','message_read','message_read_completed','ticket_read_completed','support_ticket_read_completed'}:cat='SUPPORT_MESSAGE';state='IDENTIFIABLE' if event=='message_pii_scan' or has_pii(kv) else 'REDACTED'
            elif event=='attachment_pii_scan':cat='SUPPORT_ATTACHMENT';state='PRESENT'
            elif event=='contact_lookup_completed':cat='SECONDARY_IDENTIFIER';state='PRESENT' if kv.get('rows')=='1' else 'ABSENT'
            elif event in {'contact_query_completed'}:cat='SECONDARY_IDENTIFIER';state='PRESENT' if kv.get('rows')=='1' else 'ABSENT';sys='support_platform'
            elif event in {'analytics_identity_scan','analytics_profile_read','analytics_profile_read_completed'}:cat='ANALYTICS_PROFILE';state='IDENTIFIABLE' if kv.get('direct_identifiers','0')!='0' or has_pii(kv,True) else 'ANONYMIZED'
            elif event in {'connector_heartbeat','connector_config_loaded','connector_config_read_completed'}:cat='DATA_FLOW';state='ACTIVE' if truth(kv.get('enabled')) else 'DISABLED'
            elif event in {'restore_candidate_evaluated','restore_authorization_completed','restore_entry_read_completed','restore_policy_read_completed'}:cat='BACKUP_ARCHIVE';state='BLOCKED' if kv.get('decision')=='deny' or truth(kv.get('deletion_block')) or kv.get('restore_allowed')=='false' else 'ACTIVE'
            elif event in {'export_download_check_completed','export_metadata_read_completed'}:cat='USER_EXPORT';state='PRESENT' if truth(kv.get('available')) else 'ABSENT'
            elif event=='audit_record_read_completed':cat='SECURITY_AUDIT_LOG';state='PRESENT' if kv.get('rows')=='1' else 'ABSENT'
            if cat:self.add(m,time,sys,res,cat,state,kv,loc,scope='support_replica' if 'replica' in sys else 'service')

    def document(self,m,p):
        text=subprocess.check_output(['pdftotext','-layout',str(p),'-'],text=True,timeout=30)
        if not text.strip():raise AuditError(f'PDF lacks a text layer: {m["file_id"]}; OCR required')
        found=0
        for page_no,page in enumerate(text.split('\f'),1):
            for res in set(RESOURCE.findall(page)):
                if res.startswith('support_') and re.search('attachment|correction request',text,re.I):sys,cat='support_platform','SUPPORT_ATTACHMENT'
                elif res.startswith('audit_record_') and re.search('retain until',page,re.I):sys,cat='security_service','SECURITY_AUDIT_LOG'
                else:continue
                self.add(m,m['captured_at'],sys,res,cat,'PRESENT',{'text':page},f'page {page_no}',limitations='Document text; full pages inspected during development');found+=1
        if not found:self.diagnostics.append({'file':m['file_id'],'note':'Business context has no grounded auditable resource ID; no ID invented'})

    def screenshot(self,m,p):
        version='rapidocr-3.10.0:default-models:v1'
        key=hashlib.sha256(p.read_bytes()+version.encode()).hexdigest()
        cached=self.cache/f'{key}.json' if self.cache else None
        if cached and cached.exists() and not self.no_cache:
            extracted=json.loads(cached.read_text());self.ocr_cache_hits+=1
        else:
            from rapidocr import RapidOCR
            if self.ocr_engine is None:self.ocr_engine=RapidOCR(params={'Global.log_level':'error','EngineConfig.onnxruntime.intra_op_num_threads':2,'EngineConfig.onnxruntime.inter_op_num_threads':2})
            result=self.ocr_engine(str(p));self.ocr_calls+=1
            if result.txts is None:raise AuditError(f'OCR failed for {m["file_id"]}')
            extracted=[{'text':t,'confidence':float(c),'box':b.tolist()} for b,t,c in zip(result.boxes,result.txts,result.scores)]
            if cached:cached.parent.mkdir(parents=True,exist_ok=True);cached.write_text(json.dumps(extracted))
        text='\n'.join(x['text'] for x in extracted)
        # Interpret the visible main record header only. A sidebar reference alone
        # does not prove PII exposure in the referenced record.
        from PIL import Image
        width,height=Image.open(p).size
        header=[x for x in extracted if x['box'][0][1] < 310 and x['box'][0][0]>220]
        htext='\n'.join(x['text'] for x in header)
        ids=tokens(htext);res=set(RESOURCE.findall(htext))
        mapping={'account_':('account_service','USER_PROFILE'),'marketing_':('marketing_platform','MARKETING_PROFILE'),'search_':('search_service','SEARCH_INDEX_ENTRY'),'export_':('export_service','USER_EXPORT'),'analytics_':('analytics_platform','ANALYTICS_PROFILE'),'data_flow_':('integration_service','DATA_FLOW'),'backup_':('backup_service','BACKUP_ARCHIVE'),'support_':('support_platform','SUPPORT_MESSAGE'),'audit_record_':('security_service','SECURITY_AUDIT_LOG')}
        found=0
        for r in sorted(res):
            prefix=next((k for k in mapping if r.startswith(k)),None)
            if not prefix:continue
            sys,cat=mapping[prefix]
            state='PRESENT'
            if cat=='DATA_FLOW':state='DISABLED' if re.search(r'\b(disabled|paused)\b',htext,re.I) else 'ACTIVE'
            if cat=='BACKUP_ARCHIVE':state='BLOCKED' if re.search(r'\b(blocked|denied)\b',htext,re.I) else 'ACTIVE'
            if cat in {'ANALYTICS_PROFILE','SUPPORT_MESSAGE'}:
                if not any('@' in x for x in ids):continue
                state='IDENTIFIABLE'
            if any(x['confidence']<0.7 for x in header if r in x['text']):raise AuditError(f'Low-confidence resource OCR: {m["file_id"]}')
            self.add(m,m['captured_at'],sys,r,cat,state,{'header':htext,'ocr_regions':header},'header region x>220,y<310',scope='console',limitations='OCR header; other screen regions retained in cache, not inferred as resource state');found+=1
        self.diagnostics.append({'file':m['file_id'],'ocr_regions':len(extracted),'observations':found,'note':'All regions extracted; header-derived observations only'})
