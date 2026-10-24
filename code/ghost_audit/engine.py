"""Bounded read-only investigation and deterministic policy/step planning."""
from collections import defaultdict
from dataclasses import asdict
from .schema import AuditError, Observation, timestamp, step_key, validate_steps
from .identity import IdentityIndex
from .intent import classify

ACTION_CHECK={'DELETE':('VERIFY_RECORD_ABSENT','ABSENT'),'REDACT':('VERIFY_RECORD_REDACTED','REDACTED'),'ANONYMIZE':('VERIFY_RECORD_ANONYMIZED','ANONYMIZED'),'RETAIN':('VERIFY_RECORD_PRESENT','PRESENT'),'DISABLE':('VERIFY_DATA_FLOW_DISABLED','DISABLED'),'BLOCK':('VERIFY_RESTORE_BLOCKED','BLOCKED')}
ACTION_FIX={'DELETE':'DELETE_RECORD','REDACT':'REDACT_RECORD','ANONYMIZE':'ANONYMIZE_RECORD','DISABLE':'DISABLE_DATA_FLOW','BLOCK':'BLOCK_RESTORE'}
ACTION_FIND={'DELETE':('REPORT_REMAINING_RECORD','PRESENT'),'REDACT':('REPORT_EXPOSED_PII','PRESENT'),'ANONYMIZE':('REPORT_EXPOSED_PII','PRESENT'),'DISABLE':('REPORT_ACTIVE_DATA_FLOW','ACTIVE'),'BLOCK':('REPORT_RESTORE_RISK','ACTIVE')}

class Auditor:
    def __init__(self,store,identities,history,rules,intent_model=None):
        self.store=store;self.identity=IdentityIndex(identities,history)
        self.rules={r['data_category']:r for r in rules};self.intent_model=intent_model

    def investigate(self,request):
        cutoff=timestamp(request['audit_at'])
        intent=self.intent_model.classify(request['request_text']) if self.intent_model else classify(request['request_text'])
        diagnostic={'case_id':request['case_id'],'intent':asdict(intent),'tool_calls':[],'warnings':[]}
        if not intent.authorized:return 'NOT_APPLICABLE',[],diagnostic
        uid,ids=self.identity.at(request['email'],cutoff)
        diagnostic['subject']=uid
        resources=set();observations=[]
        for ident in ids:
            for o in self.store.by_identifier.get(ident,[]):
                if o.eligible(cutoff):resources.add(o.resource)
        diagnostic['tool_calls'].append({'tool':'search_strong_identifiers','resources':len(resources)})
        # Explicit catalog links and earlier trace lookups extend ownership, never
        # numeric suffixes, filename proximity, or unrelated row positions.
        for capture,event,res,linked,eid in self.store.links:
            if timestamp(capture)<=cutoff and timestamp(event)<=cutoff and linked & ids:resources.add(res)
        for res in sorted(resources):
            observations.extend(o for o in self.store.by_resource[res] if o.eligible(cutoff))
        diagnostic['tool_calls'].append({'tool':'read_resource_history','resources':len(resources),'observations':len(observations)})
        # Complete SQL tables can establish absence only for already linked resources
        # of the same category/system, never by guessing a resource ID.
        known={o.resource:(o.system,o.category) for o in observations}
        for scope in self.store.scopes:
            if timestamp(scope.captured_at)>cutoff or timestamp(scope.observed_at)>cutoff:continue
            for res,(sys,cat) in known.items():
                if sys!=scope.system or cat!=scope.category or res in scope.resources:continue
                # A snapshot before a resource's first grounded observation says
                # nothing about the deletion outcome; it is not a post-deletion check.
                first=min(timestamp(o.observed_at) for o in observations if o.resource==res)
                if timestamp(scope.observed_at)<first:continue
                observations.append(Observation(scope.evidence_id,scope.path,scope.captured_at,scope.observed_at,sys,res,cat,'ABSENT',set(),scope.locator+' (complete table: missing key)',{},scope.scope))
        if not observations:raise AuditError(f'{request["case_id"]}: no grounded resources before cutoff')
        unresolved=resources-{o.resource for o in observations}
        if unresolved:raise AuditError(f'Linked resources lack state observations: {sorted(unresolved)}')
        if intent.prerequisites:
            # Export availability is a grounded prerequisite; no destructive plan
            # before the user-requested export is demonstrably available.
            if 'export' in intent.prerequisites and not any(o.category=='USER_EXPORT' and o.state=='PRESENT' for o in observations):
                raise AuditError('Export prerequisite not established by eligible evidence')
        by_resource=defaultdict(list)
        for o in observations:by_resource[o.resource].append(o)
        verdicts=[]
        for res,items in sorted(by_resource.items()):
            chosen=self.reconcile(items,diagnostic)
            action=self.policy(chosen,cutoff)
            wanted=ACTION_CHECK[action][1]
            compliant=chosen.state==wanted
            if action=='RETAIN' and not compliant:raise AuditError(f'Required retained resource {res} absent; schema has no restore-retained-record remediation')
            verdicts.append((chosen,action,compliant))
        if not any(o.category=='USER_PROFILE' for o,_,_ in verdicts):
            diagnostic['warnings'].append('No grounded account resource: cannot prove account deletion coverage')
        diagnostic['resources']=[{'system':o.system,'resource':o.resource,'category':o.category,'state':o.state,'action':a,'compliant':ok,'evidence':o.evidence_id,'capture':o.captured_at,'observed':o.observed_at,'locator':o.locator,'scope':o.scope} for o,a,ok in verdicts]
        status='COMPLETE' if all(ok for _,_,ok in verdicts) else 'INCOMPLETE'
        if status=='COMPLETE' and diagnostic['warnings']:raise AuditError('Cannot prove completion: '+ '; '.join(diagnostic['warnings']))
        steps=[]
        def add(phase,o,operation,state,evidence):
            steps.append({'step_no':0,'phase':phase,'system_id':o.system,'resource_id':o.resource,'operation':operation,'state':state,'evidence_id':evidence})
        for o,action,ok in verdicts:
            verify,state=ACTION_CHECK[action]
            if not ok:
                op,fs=ACTION_FIND[action];add('FINDING',o,op,fs,o.evidence_id)
                add('REMEDIATION',o,ACTION_FIX[action],state,'')
            add('VERIFICATION',o,verify,state,o.evidence_id if status=='COMPLETE' else '')
        steps.sort(key=step_key)
        for i,s in enumerate(steps,1):s['step_no']=i
        validate_steps(status,steps)
        diagnostic['tool_calls'].append({'tool':'apply_policy_and_validate','resources':len(verdicts)})
        return status,steps,diagnostic

    def reconcile(self,items,diagnostic):
        # Keep each replica's latest read separate. A primary's clean read cannot
        # establish absence from a failover or reporting replica.
        replicas=defaultdict(list)
        ordinary=[]
        for o in items:
            if any(x in o.scope for x in ['replica','failover']):replicas[o.scope].append(o)
            else:ordinary.append(o)
        def key(o):return (timestamp(o.observed_at),timestamp(o.captured_at),o.evidence_id,o.locator)
        candidates=[max(v,key=key) for v in replicas.values()]
        if ordinary:candidates.append(max(ordinary,key=key))
        if not candidates:raise AuditError('No observation candidates')
        risky=[o for o in candidates if o.state in {'PRESENT','IDENTIFIABLE','ACTIVE'} and o.category not in {'SECURITY_AUDIT_LOG','LEGAL_HOLD_RECORD'}]
        if replicas and risky:
            chosen=max(risky,key=key)
            if any(o.state!=chosen.state for o in candidates):diagnostic['warnings'].append(f'Replica disagreement for {chosen.resource}; preserve surviving copy')
            return chosen
        chosen=max(candidates,key=key)
        latest=[o for o in candidates if timestamp(o.observed_at)==timestamp(chosen.observed_at)]
        if len({o.state for o in latest})>1:raise AuditError(f'Unresolved simultaneous state conflict for {chosen.resource}')
        return chosen

    def policy(self,o,cutoff):
        if o.category=='DATA_FLOW':return 'DISABLE'
        if o.category not in self.rules:raise AuditError(f'No policy for {o.category}')
        action=self.rules[o.category]['required_action']
        if o.category=='BACKUP_ARCHIVE':return 'BLOCK'
        p=o.properties
        if action=='RETAIN':
            until=p.get('retention_until',p.get('retained_until'))
            if until and timestamp(until)<=cutoff:raise AuditError('Retention expired; supplied policy lacks an after-expiry action')
            if p.get('legal_hold_active') is False:raise AuditError('Inactive legal hold lacks a policy action')
        if o.category=='ACCOUNT_TOMBSTONE':
            if p.get('account_status','DELETED')!='DELETED':raise AuditError('Tombstone is not a deleted account')
        return action
