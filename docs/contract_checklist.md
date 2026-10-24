# Contract checklist and ambiguity register

Inspection date: 2026-10-24. Only participant-facing dataset files were read for
predictions. `dataset/` has not been modified. No private truth or generator code
was inspected. Sample answers are used only by the evaluation command.

## Inventory

- 518 evaluation requests; 32 public sample requests.
- 850 current identities; 306 identity audit changes; 4,011 global activity rows.
- 15 policy rules; 94 manifest entries and 94 files: 28 JSON, 26 logs,
  24 SQLite SQL snapshots, 11 PNG screenshots, 4 PDF documents, 1 text handover.
- Supplied raw email / SHA-256 pairs agree for all 850 current identities.
  Strong links include exact case-normalized email, validated hash, stable user
  reference, trace-correlated lookup and explicit catalog resource links.
  Names/phone numbers alone never establish ownership.
- PDF text extraction and representative screenshots were visually inspected.
  The PDF support attachment displays a resource ID and direct identifiers;
  the account console has a main account and a separate support reference;
  the reference registry retains an internal user key without direct identifiers.
- SQL exports include primary, regional, read, reporting and failover replicas.
  A primary omission never discharges a surviving copy in a replica.

## Requirements and decisions

| Requirement / ambiguity | Implemented decision |
|---|---|
| Output schema | Exactly case_id,deletion_status,steps_json; steps have exactly seven required fields |
| Phase and operation order | Explicit problem-statement table, then lexical system_id/resource_id |
| Dependency execution | Stop flows/block restores first. Output is a plan, never an executor. Real downstream dependency execution is not claimed |
| Case ordering | Lexical default because case_id is a string; `--case-sort natural` supports numeric comparison. Official numeric comparator not found |
| Reports | Canonical files in code/evaluation/, matching explicit README packaging guidance; archive also adds root evaluation/ copies to satisfy both documented paths |
| Non-deletion | Empty step array; scoped marketing-only requests are not deletion |
| Export then delete | Authorized with prerequisite; require an eligible available export before planning deletion |
| Other conditions | Fail for human review when fulfillment cannot be established |
| Time eligibility | Both manifest capture and observation time must be at/before audit_at |
| Claims | Reported workflow status and write-operation SUCCESS never establish state |
| Absence | Explicit resource readback, or same-capture primary/replica table comparison of an already-linked resource; no missing-row global assumption |
| Identity-erased resources | Do not infer association from numeric ID suffixes or sample expected outputs |
| Required retention | No deletion; missing required retained resource fails because the operation table supplies no repair operation |
| Unknown evidence / extraction failure | Fail explicitly; do not synthesize a confident output |
| AI | Locally executed RapidOCR detection/classification/recognition; no hosted LLM or paid API |
| Run failure | Normal CLI exits nonzero and does not replace output.csv. `code/review.py` creates explicitly partial review artifacts |
| Transcripts | log.txt is append-only summary; agent-trace.zip is separate raw-session export after quitting Codex |

## Official event check

Official sources consulted:
- https://help.hackerrank.com/articles/3728112689-hackerrank-orchestrate
- https://www.hackerrank.com/hackerrank-orchestrate-october26

The official October page gives a start of 2026-10-24 12:30 UTC (18:30 Dhaka)
and describes a 24-hour event. This suggests the following day at the same time,
but an explicit closing timestamp was not verified. The repository has no end
time. Do not present the inferred end time as confirmed. Exact edition-specific
scoring weights were not established from the consulted sources.

## Hand traces from public evidence

1. Simple incomplete (case_05): supplied email matches the user reference in
   `evidence_54`, table `customer_profiles_failover_replica`, resource
   `account_005`. Primary is empty for that key, replica contains the profile.
   USER_PROFILE requires DELETE: finding PRESENT, delete, verify absent.
   The sample and computed sequence agree exactly.
2. Recreation risk (case_15): `evidence_01` connector read/heartbeat establishes
   enabled `data_flow_9846` using the subject selector. The same trace export
   supplies the account lookup and retained security record. Report active flow,
   disable it, then verify account absence, security retention and disabled flow.
3. Complete example (case_03): complete account absence and retained audit evidence
   can be inspected in the emitted diagnostic. Public sample also expects an
   anonymized analytics resource; its missing identity association is reported as
   a sample coverage mismatch. This is an honest incomplete trace of the expected
   proof, not a claim that every expected link can be reconstructed.

The public samples contain no NOT_APPLICABLE requests. Independent synthetic
fixtures cover that class, multilingual negation, mixed requests and conditions.
