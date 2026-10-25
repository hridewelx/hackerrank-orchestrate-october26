"""Eligible identity knowledge and alias ownership intervals, separate from PII detection."""
import hashlib
import re
from collections import defaultdict
from .schema import AuditError, timestamp

TOKEN=re.compile(r'[\w.+%-]+@[\w.-]+\.[A-Za-z]{2,}|\b[a-fA-F0-9]{64}\b|\buser_\d+\b',re.UNICODE)
RESOURCE=re.compile(r'\b(?:account|analytics|search|support|audit_record|data_flow|backup|export|marketing|tombstone|legal_hold|cache|email_delivery|secondary_identifier|telemetry)_\d+\b')

def normalize_email(value):
    return value.strip().lower()

def tokens(value):
    """Strong retrieval tokens only: names and phone numbers never establish a link."""
    if isinstance(value,dict): return set().union(*(tokens(v) for v in value.values())) if value else set()
    if isinstance(value,list): return set().union(*(tokens(v) for v in value)) if value else set()
    return {x.lower() for x in TOKEN.findall(str(value))}

class IdentityIndex:
    def __init__(self, identities, history):
        self.identities=identities;self.history=history;self._views={}
        self.hash_verified=bool(identities) and all(hashlib.sha256(r['email'].encode()).hexdigest()==r['email_hash'] for r in identities)

    def view(self,cutoff):
        key=cutoff.isoformat() if cutoff else 'all'
        if key in self._views:return self._views[key]
        snapshots=[r for r in self.identities if cutoff is None or timestamp(r['updated_at'])<=cutoff]
        events=[e for e in self.history if cutoff is None or timestamp(e['event_time'])<=cutoff]
        aliases=defaultdict(lambda:defaultdict(set));claims=defaultdict(list)
        for e in sorted(events,key=lambda e:(e['event_time'],e['audit_id'])):
            field=e['field_name'];uid=e['user_id'];when=timestamp(e['event_time'])
            if field not in {'email','email_hash','phone','name'}:continue
            old,new=e['old_value'],e['new_value']
            for raw in [old,new]:
                if raw:aliases[uid][field].add(raw)
            if field in {'email','email_hash'}:
                norm=lambda s:s.strip().lower()
                if old:
                    # This eligible event establishes prior ownership, even if its
                    # start is unknown. Close an earlier new-value interval.
                    found=False
                    for c in claims[norm(old)]:
                        if c['uid']==uid and c['end'] is None:c['end']=when;found=True
                    if not found:claims[norm(old)].append(dict(uid=uid,start=None,end=when,source=e['audit_id']))
                if new:claims[norm(new)].append(dict(uid=uid,start=when,end=None,source=e['audit_id']))
        for r in snapshots:
            uid=r['user_id'];when=timestamp(r['updated_at'])
            for field in ['email','email_hash','phone','name']:
                raw=r.get(field)
                if raw:aliases[uid][field].add(raw)
                if raw and field in {'email','email_hash'}:
                    value=raw.strip().lower()
                    if not any(c['uid']==uid for c in claims[value]):
                        claims[value].append(dict(uid=uid,start=when,end=None,source='identity snapshot'))
        verified=bool(snapshots) and all(hashlib.sha256(r['email'].encode()).hexdigest()==r['email_hash'] for r in snapshots)
        strong={}
        for uid,a in aliases.items():
            strong[uid]={uid}|{normalize_email(v) for v in a['email']}|{v.strip().lower() for v in a['email_hash']}
            if verified:
                for email in a['email']:
                    hashed=hashlib.sha256(email.encode()).hexdigest();strong[uid].add(hashed)
                    # Derived hashes inherit the alias's eligible ownership intervals.
                    claims[hashed].extend(dict(c) for c in claims[normalize_email(email)] if c['uid']==uid)
        result=(aliases,claims,strong,events);self._views[key]=result;return result

    @staticmethod
    def owners(claims,when):
        return {c['uid'] for c in claims if (c['start'] is None or c['start']<=when) and (c['end'] is None or when<c['end'])}

    def resolve(self,email,cutoff=None,requested_at=None):
        _,claims,strong,_=self.view(cutoff)
        value=normalize_email(email)
        candidates={uid for uid,ids in strong.items() if value in ids and '@' in value}
        if len(candidates)>1 and requested_at is not None:
            when=timestamp(requested_at) if isinstance(requested_at,str) else requested_at
            candidates &= self.owners(claims[value],when)
        if len(candidates)!=1:raise AuditError(f'Identity resolution found {len(candidates)} subjects from eligible identity knowledge')
        return next(iter(candidates))

    def aliases(self,uid,cutoff=None):
        aliases,_,_,_=self.view(cutoff)
        return {field:sorted(aliases[uid][field]) for field in ['email','email_hash','phone','name']}

    def warnings(self,uid,requested_at,cutoff=None):
        requested=timestamp(requested_at);events=self.view(cutoff)[3]
        return [f"Email change {e['audit_id']} at {e['event_time']} is after requested_at but available by audit_at"
                for e in events if e['user_id']==uid and e['field_name']=='email' and timestamp(e['event_time'])>requested]

    def at(self,email,cutoff=None,requested_at=None):
        uid=self.resolve(email,cutoff,requested_at)
        return uid,self.view(cutoff)[2][uid]

    def matches(self,uid,identifiers,observed_at,cutoff):
        stable={i for i in identifiers if re.fullmatch(r'user_\d+',i)}
        if stable:return stable=={uid}
        _,claims,strong,_=self.view(cutoff)
        when=timestamp(observed_at) if isinstance(observed_at,str) else observed_at
        for value in identifiers & strong.get(uid,set()):
            owners={c['uid'] for c in claims[value]}
            if len(owners)<=1 or self.owners(claims[value],when)=={uid}:return True
        return False
