"""Read-only. Validates output.csv against the published contract and explains
why rows have empty steps.  Usage: python3 diagnose_unresolved.py [repo_root] [output.csv]
Never modifies any file."""
import collections
import csv
import json
import sys
from pathlib import Path

ROOT = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(".")
OUT = Path(sys.argv[2]) if len(sys.argv) > 2 else ROOT / "output.csv"
DS = ROOT / "dataset"

# (operation -> (phase, state)), in the published operation order
OPS = [
    ("REPORT_REMAINING_RECORD", "FINDING", "PRESENT"),
    ("REPORT_EXPOSED_PII", "FINDING", "PRESENT"),
    ("REPORT_ACTIVE_DATA_FLOW", "FINDING", "ACTIVE"),
    ("REPORT_RESTORE_RISK", "FINDING", "ACTIVE"),
    ("DISABLE_DATA_FLOW", "REMEDIATION", "DISABLED"),
    ("BLOCK_RESTORE", "REMEDIATION", "BLOCKED"),
    ("DELETE_RECORD", "REMEDIATION", "ABSENT"),
    ("REDACT_RECORD", "REMEDIATION", "REDACTED"),
    ("ANONYMIZE_RECORD", "REMEDIATION", "ANONYMIZED"),
    ("VERIFY_RECORD_ABSENT", "VERIFICATION", "ABSENT"),
    ("VERIFY_RECORD_PRESENT", "VERIFICATION", "PRESENT"),
    ("VERIFY_RECORD_REDACTED", "VERIFICATION", "REDACTED"),
    ("VERIFY_RECORD_ANONYMIZED", "VERIFICATION", "ANONYMIZED"),
    ("VERIFY_DATA_FLOW_DISABLED", "VERIFICATION", "DISABLED"),
    ("VERIFY_RESTORE_BLOCKED", "VERIFICATION", "BLOCKED"),
]
OP_IDX = {o: i for i, (o, _, _) in enumerate(OPS)}
OP_META = {o: (p, s) for o, p, s in OPS}
PH_IDX = {"FINDING": 0, "REMEDIATION": 1, "VERIFICATION": 2}
FIELDS = {"step_no", "phase", "system_id", "resource_id", "operation", "state", "evidence_id"}


def read(p):
    with open(p, encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


req = {r["case_id"]: r for r in read(DS / "deletion_requests.csv")}
ids = read(DS / "user_identities.csv")
aud = read(DS / "user_audit_log.csv")
raw_cur = {u["email"] for u in ids}
norm_cur = {u["email"].strip().lower() for u in ids}
old_email = {a["old_value"].strip().lower() for a in aud if a["field_name"] == "email"}

with open(OUT, encoding="utf-8", newline="") as f:
    reader = csv.DictReader(f)
    header = reader.fieldnames
    rows = list(reader)

problems = []
if header != ["case_id", "deletion_status", "steps_json"]:
    problems.append(f"header is {header}")
seen = [r["case_id"] for r in rows]
if len(rows) != len(req):
    problems.append(f"{len(rows)} rows, expected {len(req)}")
if len(set(seen)) != len(seen):
    problems.append("duplicate case_ids")
if set(seen) != set(req):
    problems.append(f"case_id set differs: missing {len(set(req) - set(seen))}, extra {len(set(seen) - set(req))}")
num = lambda c: int(c.split("_")[1])
print("row order: numeric=%s lexicographic=%s" % (seen == sorted(seen, key=num), seen == sorted(seen)))

empty_rows, na_rows = [], []
for r in rows:
    cid, status = r["case_id"], r["deletion_status"]
    if status not in {"COMPLETE", "INCOMPLETE", "NOT_APPLICABLE"}:
        problems.append(f"{cid}: bad status {status!r}")
    try:
        steps = json.loads(r["steps_json"])
        assert isinstance(steps, list)
    except Exception:
        problems.append(f"{cid}: steps_json is not a JSON array")
        continue
    if status == "NOT_APPLICABLE":
        na_rows.append(cid)
        if steps:
            problems.append(f"{cid}: NOT_APPLICABLE must have []")
    elif not steps:
        empty_rows.append(cid)  # contract-valid JSON, but wrong content for COMPLETE/INCOMPLETE
    keys = []
    for i, s in enumerate(steps, 1):
        if set(s) != FIELDS:
            problems.append(f"{cid}: step {i} fields {sorted(set(s) ^ FIELDS)} differ")
            continue
        if s["step_no"] != i:
            problems.append(f"{cid}: step_no {s['step_no']} at position {i}")
        if s["operation"] not in OP_META:
            problems.append(f"{cid}: step {i} invalid operation {s['operation']!r}")
            continue
        if OP_META[s["operation"]] != (s["phase"], s["state"]):
            problems.append(f"{cid}: step {i} phase/state do not match operation")
        if (s["phase"] == "FINDING") == (s["evidence_id"] == "") and status == "INCOMPLETE":
            problems.append(f"{cid}: step {i} evidence_id rule (INCOMPLETE: findings cite, rest empty)")
        if status == "COMPLETE" and (s["phase"] != "VERIFICATION" or not s["evidence_id"]):
            problems.append(f"{cid}: COMPLETE needs evidence-cited VERIFICATION only")
        keys.append((PH_IDX[s["phase"]], OP_IDX[s["operation"]], s["system_id"], s["resource_id"]))
    if keys != sorted(keys):
        problems.append(f"{cid}: steps not in published order")

print(f"rows={len(rows)}  NOT_APPLICABLE={len(na_rows)}  empty-steps COMPLETE/INCOMPLETE={len(empty_rows)}")
print(f"contract problems: {len(problems)}")
for p in problems[:25]:
    print("  -", p)

buckets = collections.defaultdict(list)
for cid in empty_rows:
    q = req.get(cid)
    if not q:
        continue
    e = q["email"]
    if e in raw_cur:
        b = "email matches a current identity exactly"
    elif e.strip().lower() in norm_cur:
        b = "email matches only after trim/lowercase"
    elif e.strip().lower() in old_email:
        b = "email is a HISTORICAL email (audit log old_value)"
    else:
        b = "email not found anywhere in identities/audit log"
    lang = "ASCII text" if all(ord(c) < 128 for c in q["request_text"]) else "non-ASCII text"
    buckets[(b, lang, q["reported_status"])].append(cid)
print("\nWhy are the empty rows empty?  (email link x text x reported_status)")
for k, v in sorted(buckets.items(), key=lambda kv: -len(kv[1])):
    print(f"  {len(v):4d}  {k[0]} | {k[1]} | {k[2]} | e.g. {v[:4]}")

print("\nNOT_APPLICABLE rows - request text (check these really are non-deletion):")
for cid in na_rows:
    print("  ", cid, req[cid]["request_text"][:90].replace("\n", " "))
