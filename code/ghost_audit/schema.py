"""Strict observations and challenge serialization contract."""
from dataclasses import dataclass, field
from datetime import datetime
import csv
import re

OPERATIONS = {
 'FINDING': [('REPORT_REMAINING_RECORD','PRESENT'),('REPORT_EXPOSED_PII','PRESENT'),('REPORT_ACTIVE_DATA_FLOW','ACTIVE'),('REPORT_RESTORE_RISK','ACTIVE')],
 'REMEDIATION': [('DISABLE_DATA_FLOW','DISABLED'),('BLOCK_RESTORE','BLOCKED'),('DELETE_RECORD','ABSENT'),('REDACT_RECORD','REDACTED'),('ANONYMIZE_RECORD','ANONYMIZED')],
 'VERIFICATION': [('VERIFY_RECORD_ABSENT','ABSENT'),('VERIFY_RECORD_PRESENT','PRESENT'),('VERIFY_RECORD_REDACTED','REDACTED'),('VERIFY_RECORD_ANONYMIZED','ANONYMIZED'),('VERIFY_DATA_FLOW_DISABLED','DISABLED'),('VERIFY_RESTORE_BLOCKED','BLOCKED')],
}
FIELDS = ('step_no','phase','system_id','resource_id','operation','state','evidence_id')
HEADER = ('case_id','deletion_status','steps_json')

class AuditError(ValueError): pass

def timestamp(value):
    result = datetime.fromisoformat(value.replace('Z','+00:00'))
    if result.tzinfo is None: raise AuditError(f'Timestamp lacks timezone: {value}')
    return result

def read_csv(path):
    with path.open(encoding='utf-8-sig', newline='') as f: return list(csv.DictReader(f))

def natural_key(value):
    return tuple(int(x) if x.isdigit() else x for x in re.split(r'(\d+)', value))

def step_key(s):
    phase=s['phase']
    return (list(OPERATIONS).index(phase),[x[0] for x in OPERATIONS[phase]].index(s['operation']),s['system_id'],s['resource_id'])

@dataclass
class Observation:
    evidence_id: str
    path: str
    captured_at: str
    observed_at: str
    system: str
    resource: str
    category: str
    state: str
    identifiers: set[str]
    locator: str
    properties: dict = field(default_factory=dict)
    scope: str = 'service'
    complete: bool = True
    limitations: str = ''

    def eligible(self, cutoff):
        return timestamp(self.captured_at)<=cutoff and timestamp(self.observed_at)<=cutoff

@dataclass
class Scope:
    evidence_id: str
    path: str
    captured_at: str
    observed_at: str
    system: str
    category: str
    resources: set[str]
    locator: str
    scope: str

def validate_steps(status, steps):
    if status not in {'COMPLETE','INCOMPLETE','NOT_APPLICABLE'}: raise AuditError('Invalid status')
    if not isinstance(steps,list): raise AuditError('Steps must be array')
    if status=='NOT_APPLICABLE' and steps: raise AuditError('Non-deletion has steps')
    if status=='COMPLETE' and not steps: raise AuditError('Completion requires proof')
    if status=='INCOMPLETE' and not any(x['phase']=='FINDING' for x in steps): raise AuditError('Incomplete requires findings')
    for i,s in enumerate(steps,1):
        if set(s)!=set(FIELDS) or s['step_no']!=i: raise AuditError('Invalid step fields/number')
        if s['phase'] not in OPERATIONS or (s['operation'],s['state']) not in OPERATIONS[s['phase']]: raise AuditError('Invalid operation/state')
        if not s['system_id'] or not s['resource_id']: raise AuditError('Missing resource')
        cited=s['phase']=='FINDING' or status=='COMPLETE'
        if bool(s['evidence_id']) != cited: raise AuditError('Invalid citation presence')
        if status=='COMPLETE' and s['phase']!='VERIFICATION': raise AuditError('Complete contains non-verification')
    if steps!=sorted(steps,key=step_key): raise AuditError('Noncanonical ordering')
