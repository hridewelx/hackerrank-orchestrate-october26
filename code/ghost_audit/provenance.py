"""Content bindings for participant inputs, implementation, and generated outputs."""
import hashlib,json
from pathlib import Path
from .schema import read_csv,AuditError

def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def dataset_digest(dataset):
    dataset=Path(dataset).resolve()
    paths=[dataset/n for n in ['user_identities.csv','user_audit_log.csv','system_activity.csv','deletion_rules.csv','evidence_files.csv']]
    for row in read_csv(dataset/'evidence_files.csv'):
        p=(dataset/row['file_path']).resolve()
        if not p.is_relative_to(dataset/'evidence'):raise AuditError('Evidence path escapes dataset')
        paths.append(p)
    return hashlib.sha256(json.dumps([(str(p.relative_to(dataset)),sha(p)) for p in sorted(set(paths))]).encode()).hexdigest()

def behavior_digest():
    code=Path(__file__).resolve().parents[1]
    paths=sorted((code/'ghost_audit').glob('*.py'))+[code/'main.py',code/'validate.py']
    return hashlib.sha256(json.dumps([(str(p.relative_to(code)),sha(p)) for p in paths]).encode()).hexdigest()
