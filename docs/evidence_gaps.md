# Evidence gaps requiring review

These are reproducible implementation diagnostics, not assertions about hidden
organizer truth. They identify what the current parser/linker cannot establish.
No missing resource association is filled using a public answer lookup.

## Concrete source checks

- Public case_01 expects account_001 absent, citing evidence_54. Its SQL tables
  contain account_005 and unrelated profiles; they contain no account_001 row or
  email/user link for that resource. system_activity contains a DELETE_RECORD claim
  naming account_001, but not its owner. Deriving account_001 from user_01 would be
  the prohibited numeric-ID shortcut. The expected absent key cannot be recovered
  from a row that is not in the snapshot without another link. The same applies to
  public case_02 and case_04 (case_04 also expects `analytics_901`, whose `user_id`,
  `email`, `phone` and `email_hash` are all null).
- Public case_21 expects account_6440 and analytics_5335 in addition to the retained
  audit record. evidence_92 contains a null-profile lookup for the account and a
  sanitized analytics row, but neither carries the subject identifier needed to
  associate it with the request. Only the retained audit record is attributable, so
  the case is now `COMPLETE` from that exact-key-linked, already-compliant record
  under the documented coverage waiver — but its verification sequence is shorter
  than the expectation, which is why whole-case exact match stays at 8/32.
- Public case_24 expects retained audit_record_7095 as a future verification. Its
  record is in a bundle captured September 17, after the September 15 audit cutoff.
  The eligible evidence_92 export does not contain that security record. The
  implementation cannot discover it by reading future evidence for the case.
- Public case_07's expected output omits object_19; activity_4007 explicitly links
  that object to the subject, and evidence_46 shows the named attachment. Current
  implementation includes that additional object, lowering exact sample matching.
- Evaluation case_55 was repaired: `evidence_32` (2026-04-29) is a backup inventory
  screen showing `backup_9287` linked to the request email. The screen does not show
  the archive as blocked, so the case is an evidence-backed `INCOMPLETE` with
  `REPORT_RESTORE_RISK`, `BLOCK_RESTORE`, and `VERIFY_RESTORE_BLOCKED`.
- Evaluation case_63 is the only remaining unresolved case. `activity_4008` links
  `marketing_001` to `kwame-mensah@proton.me`, while the eligible console screenshot
  `evidence_60` displays `marketing_001` for `sj.park@naver.com`. Observed artifact
  content outranks the catalog row, so the resource is excluded and the override is
  recorded in diagnostics. No other eligible evidence mentions `user_09`, so the
  case still fails closed. It is not reported as `INCOMPLETE` with invented steps.

The catalog and screenshot can disagree on ownership. A successful catalog link is
not assumed to be infallible, and a conflicting artifact is not silently preferred:
the override, the artifact identifiers and the catalog claim are all recorded.

## Coverage waiver

Previously, any case without an attributable `USER_PROFILE`/deleted-tombstone
observation failed closed, which produced 97 empty fallbacks even when every linked
record was already compliant. The current rule asserts `COMPLETE` without account
coverage only when all of the following hold:

1. every decided record is linked by an exact key (stable user reference, current or
   historical email, verified email hash) — never a name, phone, filename, row
   position, timestamp or case identifier;
2. every decided record already has its policy-required treatment;
3. at least one such record exists.

The diagnostic records `coverage_basis` and `coverage_waiver`
(`retained-records-only` or `all-linked-records-compliant`) for every case that uses
it. On the public sample this changed 5 status misses and improved content-step F1
from 84.21% to 88.76%; see `code/evaluation/evaluation_report.md` for the full
experiment, including the positional metric that declined.

## Current full-dataset run

Attempted 518; 517 decided; unresolved 1.

| Cause | Count |
|---|---:|
| Only an eligible retained security-audit record; no attributable account profile (now `COMPLETE` via the waiver) | 78 (resolved) |
| Support/backup/flow records compliant but no attributable account profile (now `COMPLETE` via the waiver) | 19 (resolved) |
| Catalog claim contradicted by the observed artifact, and no other evidence for the subject | 1 (open) |
| **Open total** | **1** |

| Case | Diagnostic |
|---|---|
| case_63 | no grounded resources before cutoff; catalog claim outranked by observed artifact content: marketing_001 shows sj.park@naver.com |

The documented default run writes all 518 rows with this one row as `INCOMPLETE`
with `steps_json=[]`, prints a WARNING banner, marks the run `degraded: true` /
`submission_ready: false`, and writes the same information to `degraded_cases.md`.
`--strict` refuses to write anything while this case is unresolved (exit 2, prior
output byte-identical). The 98-case list from the
previous build is preserved at
`evaluation_runs/repair_session_20261025T0520Z/degraded_cases.md`.
