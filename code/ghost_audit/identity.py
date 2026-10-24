"""Time-filtered strong identity linkage; never link by numeric ID suffix or name alone."""
import hashlib
import re
from collections import defaultdict
from .schema import AuditError, timestamp

TOKEN=re.compile(r'[\w.+%-]+@[\w.-]+\.[A-Za-z]{2,}|\b[a-fA-F0-9]{64}\b|\buser_\d+\b',re.UNICODE)
RESOURCE=re.compile(r'\b(?:account|analytics|search|support|audit_record|data_flow|backup|export|marketing|tombstone|legal_hold|cache|email_delivery|secondary_identifier|telemetry)_\d+\b')

def tokens(value):
    if isinstance(value,dict): return set().union(*(tokens(v) for v in value.values())) if value else set()
    if isinstance(value,list): return set().union(*(tokens(v) for v in value)) if value else set()
    return {x.lower() for x in TOKEN.findall(str(value))}

class IdentityIndex:
    def __init__(self, identities, history):
        self.identities=identities;self.history=history
        self.hash_verified=bool(identities) and all(hashlib.sha256(r['email'].encode()).hexdigest()==r['email_hash'] for r in identities)

    def at(self, email, cutoff):
        candidates=[]
        for r in self.identities:
            ids={r['user_id']}
            events=[a for a in self.history if a['user_id']==r['user_id']]
            if timestamp(r['updated_at'])<=cutoff:
                ids |= tokens({k:r[k] for k in ['email','email_hash']})
            for a in events:
                if timestamp(a['event_time'])<=cutoff: ids |= tokens([a['old_value'],a['new_value']])
            if email.lower() in ids: candidates.append((r,ids))
        if len(candidates)!=1: raise AuditError(f'Identity resolution found {len(candidates)} subjects')
        r,ids=candidates[0]
        if self.hash_verified:
            ids |= {hashlib.sha256(x.encode()).hexdigest() for x in list(ids) if '@' in x}
        return r['user_id'],ids
