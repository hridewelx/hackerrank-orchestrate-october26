# Development evaluation

This is development evaluation, not an untouched hold-out. Public sample answers
were read during architecture and parser development. Hidden evaluation answers
were never accessed. Unresolved cases are counted as incorrect, not omitted.

| Metric | Result |
|---|---:|
| Status accuracy | 22/32 (68.75%) |
| Whole-case exact match | 8/32 (25.00%) |
| Exact ordered sequence | 8/32 (25.00%) |
| Exact-step precision | 109/140 (77.86%) |
| Exact-step recall | 109/193 (56.48%) |
| Exact-step F1 | 65.47% |
| Unmatched expected / predicted steps | 84 / 31 |
| Levenshtein step distance | 86/195 (0.4410) |

Exact-step matching uses multiset intersection over all seven fields. Sequence
distance uses unit insertion, deletion and substitution cost on complete step
tuples, divided by the sum of maximum expected/predicted sequence lengths.

Field accuracy uses ordinal position, without matching on any field under test.
Every missing/extra position adds one incorrect comparison to every field. It is
a diagnostic measure: a shifted sequence can lower many fields together.

| Field | Correct / positions | Accuracy |
|---|---:|---:|
| step_no | 138/195 | 70.77% |
| phase | 135/195 | 69.23% |
| system_id | 111/195 | 56.92% |
| resource_id | 111/195 | 56.92% |
| operation | 120/195 | 61.54% |
| state | 122/195 | 62.56% |
| evidence_id | 136/195 | 69.74% |

## Three-class confusion matrix

Unresolved is an execution outcome, not a fourth submitted status.

| Expected | COMPLETE | INCOMPLETE | NOT_APPLICABLE | Unresolved |
|---|---:|---:|---:|---:|
| COMPLETE | 1 | 0 | 0 | 9 |
| INCOMPLETE | 0 | 21 | 0 | 1 |
| NOT_APPLICABLE | 0 | 0 | 0 | 0 |

The 32 public samples contain no NOT_APPLICABLE examples. Non-deletion coverage comes from independently authored fixtures.

## Case-level failures

| Case | Expected / actual | Expected / produced steps |
|---|---|---:|
| case_01 | COMPLETE / UNRESOLVED | 1 / 0 |
| case_02 | COMPLETE / UNRESOLVED | 1 / 0 |
| case_03 | COMPLETE / COMPLETE | 3 / 2 |
| case_04 | COMPLETE / UNRESOLVED | 2 / 0 |
| case_06 | INCOMPLETE / INCOMPLETE | 4 / 3 |
| case_07 | INCOMPLETE / INCOMPLETE | 4 / 6 |
| case_08 | INCOMPLETE / INCOMPLETE | 4 / 3 |
| case_09 | INCOMPLETE / INCOMPLETE | 5 / 3 |
| case_10 | INCOMPLETE / INCOMPLETE | 4 / 3 |
| case_17 | INCOMPLETE / UNRESOLVED | 5 / 0 |
| case_18 | INCOMPLETE / INCOMPLETE | 14 / 12 |
| case_20 | INCOMPLETE / INCOMPLETE | 8 / 6 |
| case_21 | COMPLETE / UNRESOLVED | 3 / 0 |
| case_22 | INCOMPLETE / INCOMPLETE | 8 / 7 |
| case_23 | INCOMPLETE / INCOMPLETE | 8 / 6 |
| case_24 | INCOMPLETE / INCOMPLETE | 7 / 6 |
| case_25 | COMPLETE / UNRESOLVED | 3 / 0 |
| case_26 | COMPLETE / UNRESOLVED | 6 / 0 |
| case_27 | COMPLETE / UNRESOLVED | 6 / 0 |
| case_28 | COMPLETE / UNRESOLVED | 6 / 0 |
| case_29 | INCOMPLETE / INCOMPLETE | 14 / 12 |
| case_30 | INCOMPLETE / INCOMPLETE | 14 / 12 |
| case_31 | COMPLETE / UNRESOLVED | 3 / 0 |
| case_32 | INCOMPLETE / INCOMPLETE | 5 / 4 |

## Root causes and iteration

- Initial conditional-intent detection rejected ordinary “contact me if you need information” sentences. Restricting condition detection to the deletion clause removed 64 failures in the first evaluation-dataset pass.
- Cloud log envelopes escaped their inner key/value quotes. Normalizing the envelope without stripping the inner closing quote fixed false missing audit records.
- A marketing-only opt-out initially matched “remove” plus “account”; explicit scoped opt-out handling fixed that classification and is covered by regression tests.
- Treating a batch SQL inventory as a global inventory produced false absence for retained records. Absence by missing key is now restricted to a resource proven present in another table of the same capture, and only for deletable profile/search categories.
- Several public expectations name deleted/anonymized resources without an eligible identity link. The implementation deliberately does not join numeric suffixes or sample answer rows.
- Catalog links introduce additional resources not reflected in some public expected outputs (for example a separately linked object-storage attachment). The implementation investigates eligible links rather than suppressing evidence to match sample labels.
- Citation selection uses latest eligible observed time per resource scope, then capture time and stable lexical tie-breaks. It is not fitted to specific expected evidence IDs. Different valid citations can lower exact-match metrics.

## Independent synthetic cases and assumptions

`code/tests/test_audit.py` builds isolated datasets using the real CSV and JSON schemas. These are participant-authored expectations, not organizer truth. The suite covers:

1. Historical email linkage with an unrelated subject sharing a weak name/phone: only strong email/history links count.
2. English, Spanish, French, Japanese and Korean deletion, non-deletion and negation; marketing opt-out remains non-deletion.
3. Capture time after cutoff and event time after cutoff independently exclude a contradictory record.
4. Claimed workflow success cannot override a present record or a surviving failover replica.
5. A clean primary plus an active connector is incomplete; disable precedes record checks.
6. Security retention and active legal-hold records remain present; no deletion is planned.
7. Tombstones retain stable subject references; a surviving name requires redaction.
8. Blocked backups are compliant; active restore access requires blocking, never archive deletion.
9. Export-then-delete authorizes deletion with an export prerequisite. Missing prerequisite evidence fails; a present export permits the plan.
10. An unresolved conditional request fails instead of assuming the condition is true.

Metamorphic tests shuffle rows, add unrelated decoys, add post-cutoff evidence,
rename a manifest-linked path, and change an unsupported workflow status. Those
changes must leave grounded decisions unchanged. Additional tests block SQL
ATTACH and manifest traversal, reject unknown structures and empty evidence, and
validate step phases, numbering and citation rules. Run the suite for current
pass/fail results; no test result is inferred from source presence.

## Limitations

Local OCR supplies learned text detection/recognition. Intent and planning are
deterministic. No paid language-model comparison or independent generative-model
stability claim is made. Warm-cache agreement measures replay and deterministic
planning only. Runtime evidence gaps are not replaced with fabricated answers.

## Final validation record

22/22 independent unittest tests passed. The final full-dataset cold review attempted 518 requests, emitted 414 decisions and rejected 104 unresolved cases. A warm replay produced byte-identical partial predictions. All 414 emitted rows passed schema, order, citation-cutoff and provenance-locator validation. This is not a valid 518-row submission.

The final safety review added ownership-conflict rejection and stopped inferring full tombstone redaction from a reference-only console. This increased review cases from 102 to 104, and reduced sample status matches from 23 to 22; the change avoids unsupported confident conclusions.

The source ZIP was extracted into a fresh temporary directory with the original dataset supplied externally. All 22 tests passed there, a fresh OCR computation reproduced the same 414 partial rows byte-for-byte, and the normal CLI exited 2 without creating output.csv. Archive inspection found no dataset, environments, caches, nested archives or recognizable secret patterns.
