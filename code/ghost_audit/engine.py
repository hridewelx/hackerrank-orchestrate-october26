"""Bounded read-only investigation and deterministic policy/step planning."""
from collections import defaultdict
import logging
from dataclasses import asdict, replace
from .ingest import has_pii
from .schema import AuditError, Observation, timestamp, step_key, validate_steps
from .identity import IdentityIndex
from .intent import classify

ACTION_CHECK={'DELETE':('VERIFY_RECORD_ABSENT','ABSENT'),'REDACT':('VERIFY_RECORD_REDACTED','REDACTED'),'ANONYMIZE':('VERIFY_RECORD_ANONYMIZED','ANONYMIZED'),'RETAIN':('VERIFY_RECORD_PRESENT','PRESENT'),'DISABLE':('VERIFY_DATA_FLOW_DISABLED','DISABLED'),'BLOCK':('VERIFY_RESTORE_BLOCKED','BLOCKED')}
ACTION_FIX={'DELETE':'DELETE_RECORD','REDACT':'REDACT_RECORD','ANONYMIZE':'ANONYMIZE_RECORD','DISABLE':'DISABLE_DATA_FLOW','BLOCK':'BLOCK_RESTORE'}
ACTION_FIND={'DELETE':('REPORT_REMAINING_RECORD','PRESENT'),'REDACT':('REPORT_EXPOSED_PII','PRESENT'),'ANONYMIZE':('REPORT_EXPOSED_PII','PRESENT'),'DISABLE':('REPORT_ACTIVE_DATA_FLOW','ACTIVE'),'BLOCK':('REPORT_RESTORE_RISK','ACTIVE')}

COVERAGE_WAIVERS={'none','retained','compliant'}

class Auditor:
    def __init__(self,store,identities,history,rules,intent_model=None,coverage_waiver='compliant'):
        if coverage_waiver not in COVERAGE_WAIVERS:raise AuditError(f'Unknown coverage waiver {coverage_waiver}')
        self.store=store;self.identity=IdentityIndex(identities,history)
        self.rules={r['data_category']:r for r in rules};self.intent_model=intent_model
        self.coverage_waiver=coverage_waiver

    def investigate(self,request):
        diagnostic={'case_id':request['case_id'],'tool_calls':[],'warnings':[],'issues':[]}
        try:return self._investigate(request,diagnostic)
        except AuditError as error:
            diagnostic['plan_complete']=False
            error.diagnostic=diagnostic
            raise

    def _investigate(self,request,diagnostic):
        cutoff=timestamp(request['audit_at'])
        intent=self.intent_model.classify(request['request_text']) if self.intent_model else classify(request['request_text'])
        diagnostic['intent']=asdict(intent)
        if not intent.authorized:return 'NOT_APPLICABLE',[],diagnostic
        uid,ids=self.identity.at(request['email'],cutoff,request['requested_at'])
        diagnostic['subject']=uid
        diagnostic['identity_aliases']=self.identity.aliases(uid,cutoff)
        diagnostic['identity_warnings']=self.identity.warnings(uid,request['requested_at'],cutoff)
        for warning in diagnostic['identity_warnings']:
            logging.getLogger(__name__).warning('%s: %s',request['case_id'],warning)
        resources=set();observations=[];overrides=[]
        for ident in ids:
            for o in self.store.by_identifier.get(ident,[]):
                if o.eligible(cutoff) and self.identity.matches(uid,o.identifiers,o.observed_at,cutoff):resources.add(o.resource)
        diagnostic['tool_calls'].append({'tool':'search_strong_identifiers','resources':len(resources)})
        # Explicit catalog links and earlier trace lookups extend ownership, never
        # numeric suffixes, filename proximity, or unrelated row positions.
        catalog_claims=defaultdict(set)
        for capture,event,res,linked,eid in self.store.links:
            if timestamp(capture)<=cutoff and timestamp(event)<=cutoff and self.identity.matches(uid,linked,event,cutoff):
                resources.add(res);catalog_claims[res]|=set(linked)
        for res in sorted(resources):
            eligible=[o for o in self.store.by_resource[res] if o.eligible(cutoff)]
            concrete=[o for o in eligible if o.category in {'USER_PROFILE','MARKETING_PROFILE','ANALYTICS_PROFILE'} and o.identifiers and o.state not in {'ABSENT','ANONYMIZED'}]
            if concrete and not any(self.identity.matches(uid,o.identifiers,o.observed_at,cutoff) for o in eligible):
                # Observed artifact content outranks an activity catalog row. The
                # record itself names a different person, so it is not this
                # subject's copy and must not be planned against. The override is
                # recorded rather than silently ignored.
                overrides.append({'resource':res,'artifact_system':concrete[0].system,'artifact_category':concrete[0].category,
                    'artifact_identifiers':sorted(concrete[0].identifiers),'artifact_evidence':concrete[0].evidence_id,
                    'catalog_claim':sorted(catalog_claims.get(res,set()))})
                continue
            observations.extend(o for o in self.store.by_resource[res] if o.eligible(cutoff))
        if overrides:resources-= {x['resource'] for x in overrides}
        diagnostic['ownership_overrides']=overrides
        diagnostic['tool_calls'].append({'tool':'read_resource_history','resources':len(resources),'observations':len(observations)})
        # Complete SQL tables can establish absence only for already linked resources
        # of the same category/system, never by guessing a resource ID.
        known={o.resource:(o.system,o.category) for o in observations}
        for scope in self.store.scopes:
            if timestamp(scope.captured_at)>cutoff or timestamp(scope.observed_at)>cutoff:continue
            for res,(sys,cat) in known.items():
                if sys!=scope.system or cat!=scope.category or res in scope.resources:continue
                if cat not in {'USER_PROFILE','SEARCH_INDEX_ENTRY'}:continue
                # Batch inventories are scoped captures, not a global list. A
                # membership omission only discharges another copy in that capture.
                if not any(o.resource==res and o.evidence_id==scope.evidence_id for o in observations):continue
                # A snapshot before a resource's first grounded observation says
                # nothing about the deletion outcome; it is not a post-deletion check.
                first=min(timestamp(o.observed_at) for o in observations if o.resource==res)
                if timestamp(scope.observed_at)<first:continue
                observations.append(Observation(scope.evidence_id,scope.path,scope.captured_at,scope.observed_at,sys,res,cat,'ABSENT',set(),scope.locator+' (complete table: missing key)',{},scope.scope))
        if not observations:
            note=''
            if overrides:
                note='; catalog claim outranked by observed artifact content: '+', '.join(
                    f"{x['resource']} shows {', '.join(x['artifact_identifiers']) or 'no identifier'}" for x in overrides)
            raise AuditError('; '.join(diagnostic['issues']) or f'{request["case_id"]}: no grounded resources before cutoff'+note)
        unresolved=resources-{o.resource for o in observations}
        if unresolved:diagnostic['issues'].append(f'Linked resources lack state observations: {sorted(unresolved)}')
        if intent.prerequisites:
            # Export availability is a grounded prerequisite; no destructive plan
            # before the user-requested export is demonstrably available.
            if 'export' in intent.prerequisites and not any(o.category=='USER_EXPORT' and o.state=='PRESENT' for o in observations):
                diagnostic['issues'].append('Export prerequisite not established by eligible evidence')
        by_resource=defaultdict(list)
        for o in observations:
            if o.category in {'SUPPORT_MESSAGE','ACCOUNT_TOMBSTONE','EMAIL_DELIVERY_LOG','ANALYTICS_PROFILE','PRODUCT_TELEMETRY'} and o.state not in {'ABSENT'}:
                stable=o.category in {'ANALYTICS_PROFILE','PRODUCT_TELEMETRY'}
                if has_pii(o.properties,stable,diagnostic['identity_aliases'],uid):
                    o=replace(o,state='IDENTIFIABLE')
            by_resource[o.resource].append(o)
        verdicts=[]
        for res,items in sorted(by_resource.items()):
            chosen=self.reconcile(items,diagnostic)
            action=self.policy(chosen,cutoff)
            wanted=ACTION_CHECK[action][1]
            compliant=chosen.state==wanted
            if action=='RETAIN' and not compliant:
                diagnostic['issues'].append(f'Required retained resource {res} absent; schema has no restore-retained-record remediation')
                continue
            verdicts.append((chosen,action,compliant))
        covered=any(self.account_coverage(o) for o,_,_ in verdicts)
        if not covered:
            compliant=bool(verdicts) and all(ok for _,_,ok in verdicts)
            retained_only=compliant and all(a=='RETAIN' for _,a,_ in verdicts)
            exact=self.exact_key_grounded(uid,[o for o,_,_ in verdicts],cutoff)
            waived=compliant and exact and (
                self.coverage_waiver=='compliant' or (self.coverage_waiver=='retained' and retained_only))
            if waived:
                # Every record the subject is exact-key linked to already has its
                # required treatment, and no attributable account-profile row exists
                # to cite. Completion is asserted from those grounded checks only.
                diagnostic['coverage_basis']='Exact-key linked records only; required treatment already in place; no attributable account-profile observation'
                diagnostic['coverage_waiver']='retained-records-only' if retained_only else 'all-linked-records-compliant'
            else:
                diagnostic['warnings'].append('No grounded account resource: cannot prove account deletion coverage')
        diagnostic['resources']=[{'system':o.system,'resource':o.resource,'category':o.category,'state':o.state,'action':a,'compliant':ok,'evidence':o.evidence_id,'capture':o.captured_at,'observed':o.observed_at,'locator':o.locator,'scope':o.scope} for o,a,ok in verdicts]
        status='COMPLETE' if all(ok for _,_,ok in verdicts) else 'INCOMPLETE'
        if status=='COMPLETE' and diagnostic['warnings']:diagnostic['issues'].append('Cannot prove completion: '+ '; '.join(diagnostic['warnings']))
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
        diagnostic['partial_steps']=steps
        if diagnostic['issues']:raise AuditError('; '.join(diagnostic['issues']))
        validate_steps(status,steps)
        diagnostic['plan_complete']=True
        diagnostic['tool_calls'].append({'tool':'apply_policy_and_validate','resources':len(verdicts)})
        return status,steps,diagnostic

    def exact_key_grounded(self,uid,observations,cutoff):
        """True only when every decided record carries a strong exact key for the subject.

        Strong keys are the stable user reference, current/historical email and the
        verified email hash. Names, phone numbers, filenames, row positions and case
        identifiers never qualify.
        """
        if not observations:return False
        strong=self.identity.view(cutoff)[2].get(uid,set())|{uid}
        return all(o.identifiers & strong for o in observations)

    @staticmethod
    def account_coverage(o):
        # A physical deleted-account tombstone is an allowed account state, not
        # a synthetic absence inferred from search failure or ID suffixes.
        return o.category=='USER_PROFILE' or (o.category=='ACCOUNT_TOMBSTONE'
            and o.properties.get('account_status')=='DELETED'
            and {'name','email','phone','email_hash'}<=o.properties.keys())

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
            if p.get('account_status')!='DELETED':raise AuditError('Tombstone is not a deleted account')
        return action
