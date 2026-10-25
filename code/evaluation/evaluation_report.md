# Development evaluation

This is development evaluation, not an untouched hold-out. Public sample answers
were read during architecture and parser development. Hidden evaluation answers
were never accessed. All cases are evaluated, including conservative fallback predictions.
Fallback rows in this sample run: 3 (`case_01`, `case_02`, `case_04`).

| Metric | Result |
|---|---:|
| Status accuracy | 29/32 (90.62%) |
| Whole-case exact match | 8/32 (25.00%) |
| Exact ordered sequence | 8/32 (25.00%) |
| Exact-step precision | 112/163 (68.71%) |
| Exact-step recall | 112/193 (58.03%) |
| Exact-step F1 | 62.92% |
| Content-step precision (step_no excluded) | 158/163 (96.93%) |
| Content-step recall (step_no excluded) | 158/193 (81.87%) |
| Content-step F1 (step_no excluded) | 88.76% |
| Unmatched expected / predicted steps | 81 / 51 |
| Levenshtein step distance | 85/197 (0.4315) |

Exact-step matching uses multiset intersection over all seven fields, `step_no`
included, so a correct check at a different index cannot match. Content-step
matching drops `step_no` because it is positional; ordering is already measured by
the ordered-sequence and Levenshtein metrics. Both are reported for every run.
Sequence distance uses unit insertion, deletion and substitution cost on complete
step tuples, divided by the sum of maximum expected/predicted sequence lengths.

Field accuracy uses ordinal position, without matching on any field under test.
Every missing/extra position adds one incorrect comparison to every field. It is
a diagnostic measure: a shifted sequence can lower many fields together.

| Field | Correct / positions | Accuracy |
|---|---:|---:|
| step_no | 159/197 | 80.71% |
| phase | 156/197 | 79.19% |
| system_id | 114/197 | 57.87% |
| resource_id | 114/197 | 57.87% |
| operation | 123/197 | 62.44% |
| state | 125/197 | 63.45% |
| evidence_id | 157/197 | 79.70% |

## Three-class confusion matrix

Unresolved is an execution outcome, not a fourth submitted status.

| Expected | COMPLETE | INCOMPLETE | NOT_APPLICABLE | Unresolved |
|---|---:|---:|---:|---:|
| COMPLETE | 7 | 3 | 0 | 0 |
| INCOMPLETE | 0 | 22 | 0 | 0 |
| NOT_APPLICABLE | 0 | 0 | 0 | 0 |

The 32 public samples contain no NOT_APPLICABLE examples. Non-deletion coverage comes from independently authored fixtures.

## Case-level failures

| Case | Expected / actual | Expected / produced steps |
|---|---|---:|
| case_01 | COMPLETE / INCOMPLETE | 1 / 0 |
| case_02 | COMPLETE / INCOMPLETE | 1 / 0 |
| case_03 | COMPLETE / COMPLETE | 3 / 2 |
| case_04 | COMPLETE / INCOMPLETE | 2 / 0 |
| case_06 | INCOMPLETE / INCOMPLETE | 4 / 3 |
| case_07 | INCOMPLETE / INCOMPLETE | 4 / 6 |
| case_08 | INCOMPLETE / INCOMPLETE | 4 / 3 |
| case_09 | INCOMPLETE / INCOMPLETE | 5 / 3 |
| case_10 | INCOMPLETE / INCOMPLETE | 4 / 3 |
| case_17 | INCOMPLETE / INCOMPLETE | 5 / 7 |
| case_18 | INCOMPLETE / INCOMPLETE | 14 / 12 |
| case_20 | INCOMPLETE / INCOMPLETE | 8 / 6 |
| case_21 | COMPLETE / COMPLETE | 3 / 1 |
| case_22 | INCOMPLETE / INCOMPLETE | 8 / 7 |
| case_23 | INCOMPLETE / INCOMPLETE | 8 / 6 |
| case_24 | INCOMPLETE / INCOMPLETE | 7 / 6 |
| case_25 | COMPLETE / COMPLETE | 3 / 1 |
| case_26 | COMPLETE / COMPLETE | 6 / 4 |
| case_27 | COMPLETE / COMPLETE | 6 / 4 |
| case_28 | COMPLETE / COMPLETE | 6 / 4 |
| case_29 | INCOMPLETE / INCOMPLETE | 14 / 12 |
| case_30 | INCOMPLETE / INCOMPLETE | 14 / 12 |
| case_31 | COMPLETE / COMPLETE | 3 / 2 |
| case_32 | INCOMPLETE / INCOMPLETE | 5 / 4 |

## Root causes and iteration

- Initial conditional-intent detection rejected ordinary “contact me if you need information” sentences. Restricting condition detection to the deletion clause removed 64 failures in the first evaluation-dataset pass.
- Cloud log envelopes escaped their inner key/value quotes. Normalizing the envelope without stripping the inner closing quote fixed false missing audit records.
- A marketing-only opt-out initially matched “remove” plus “account”; explicit scoped opt-out handling fixed that classification and is covered by regression tests.
- Treating a batch SQL inventory as a global inventory produced false absence for retained records. Absence by missing key is now restricted to a resource proven present in another table of the same capture, and only for deletable profile/search categories.
- Several public expectations name deleted/anonymized resources without an eligible identity link. The implementation deliberately does not join numeric suffixes or sample answer rows.
- Catalog links introduce additional resources not reflected in some public expected outputs (for example a separately linked object-storage attachment). The implementation investigates eligible links rather than suppressing evidence to match sample labels.
- Citation selection uses latest eligible observed time per resource scope, then capture time and stable lexical tie-breaks. It is not fitted to specific expected evidence IDs. Different valid citations can lower exact-match metrics.
- The account-coverage guard used to fail closed whenever no attributable `USER_PROFILE` row existed, even when every linked record was already compliant. That produced 97 empty fallbacks and 8 status misses on the public sample. The coverage waiver below removes this specific failure mode without inventing observations.

## Sample status misses and the always-INCOMPLETE baseline

The always-`INCOMPLETE` baseline (every case predicted `INCOMPLETE`) scores
**22/32 (68.75%)** on status, because 22 of the 32 public samples are `INCOMPLETE`.
It emits no steps, so its step precision, recall and F1 are 0. Every result below
must therefore be read against 22/32, not against 0/32.

At the previous build (24/32) the eight status misses were:

| Case | Expected | Produced | Root cause |
|---|---|---|---|
| `case_21` | COMPLETE | INCOMPLETE | Coverage guard: only `audit_record_3737` (RETAIN, present) is attributable; `account_6440` appears only as a 404 row that carries no identity key |
| `case_25` | COMPLETE | INCOMPLETE | Same guard; `account_3136` has the same unattributable 404 shape |
| `case_26` | COMPLETE | INCOMPLETE | Same guard on a five-record set that was already compliant (retained, redacted, blocked, disabled) |
| `case_27` | COMPLETE | INCOMPLETE | Same guard, same compliant record set shape |
| `case_28` | COMPLETE | INCOMPLETE | Same guard, same compliant record set shape |
| `case_01` | COMPLETE | INCOMPLETE | No eligible evidence contains any identifier of the subject. `evidence_54` shows no `account_001` row, and the capture declares no scope, so absence cannot be attributed |
| `case_02` | COMPLETE | INCOMPLETE | Same shape: the subject appears nowhere in the eligible capture |
| `case_04` | COMPLETE | INCOMPLETE | Same shape plus `analytics_901`, whose `user_id`, `email`, `phone` and `email_hash` are all null; the expected ANONYMIZED check cannot be attributed |

The five guard cases now return `COMPLETE` with the grounded verification checks that
are actually attributable (one to five steps each). The three remaining misses are
dataset-attribution gaps: their expected answers cite records that carry no
participant-visible key to the subject, and the subject's own key never appears in
the eligible capture. Attributing them would require the request ordinal or resource
suffix join that the contract forbids, so they stay fallbacks.

## Coverage waiver experiment

Hypothesis: when exact-key evidence (stable user reference, current/historical email,
verified email hash) links the subject only to records that already have their
required treatment, the case is `COMPLETE` with grounded `VERIFY_RECORD_PRESENT`
(and sibling verification) steps instead of `INCOMPLETE` with `steps_json=[]`.
No case ID, timestamp, filename or row-position rule is involved; the waiver is
computed from identity linkage and policy state only.

`code/evaluation/coverage_experiment.py` runs the identical evidence through three
policies:

| Policy | Status accuracy | Content-step F1 | Positional-step F1 | Unmatched predicted |
|---|---:|---:|---:|---:|
| `none` (previous behaviour) | 24/32 (75.00%) | 84.21% | 65.50% | 37 |
| `retained` (retained records only) | 26/32 (81.25%) | 84.88% | 65.12% | 39 |
| `compliant` (every linked record compliant) | **29/32 (90.62%)** | **88.76%** | 62.92% | 51 |

Adopted: `compliant`. It improves status accuracy by five cases and content-step
precision (96.64% to 96.93%), recall (74.61% to 81.87%) and F1 (84.21% to 88.76%).

The positional F1 falls from 65.50% to 62.92%, and this is reported rather than
hidden. That metric includes `step_no` in the matched tuple, so the added checks can
never score unless they land on the same index; they cannot, because the
unattributable account/anonymized verification steps that precede them are missing.
The added steps themselves are correct: content-step precision stays above 96%, and
unmatched expected steps are unchanged at 81. The ordered-sequence and Levenshtein
metrics already measure position, so the content metric is the step-level gate.
Whole-case exact match is unchanged at 8/32 either way.

## Independent synthetic cases and assumptions

`code/tests/test_audit.py` and `code/tests/test_review_repairs.py` build isolated
datasets using the real CSV and JSON schemas. These are participant-authored
expectations, not organizer truth. The 69-test suite covers:

1. Historical email linkage with an unrelated subject sharing a weak name/phone: only strong email/history links count.
2. English, Spanish, Portuguese, French, Japanese and Korean deletion, non-deletion and negation; marketing opt-out remains non-deletion.
3. Advice/hypothetical questions, mailing/access/update requests, retention exceptions, and export prerequisites.
4. Capture time after cutoff and event time after cutoff independently exclude a contradictory record.
5. Claimed workflow success cannot override a present record or a surviving failover replica.
6. A clean primary plus an active connector is incomplete; disable precedes record checks.
7. Security retention and active legal-hold records remain present; no deletion is planned.
8. Tombstones retain stable subject references; a surviving name requires redaction.
9. Reference-only tombstone screens establish a deleted account; a visible direct identifier still requires redaction.
10. A backup inventory screen with an account-linked archive requires a restore block.
11. Blocked backups are compliant; active restore access requires blocking, never archive deletion.
12. Export-then-delete authorizes deletion with an export prerequisite. Missing prerequisite evidence fails; a present export permits the plan.
13. An unresolved conditional request fails instead of assuming the condition is true.
14. A retained-only, exact-key-linked record set yields `COMPLETE` with `VERIFY_RECORD_PRESENT`; the same case fails closed under the `none` policy.
15. The waiver is refused when any linked record is non-compliant, or when a decided record carries no exact key (name-only, empty or mixed).
16. Observed artifact content outranks a catalog claim: a record naming another person is excluded and the override is recorded; a record whose own key matches keeps the claim.
17. `--allow-degraded` writes a best-effort 518-row file only when requested, reports `submission_ready: false`, and the strict path still refuses to overwrite root `output.csv`.

Metamorphic tests shuffle rows, add unrelated decoys, add post-cutoff evidence,
rename a manifest-linked path, and change an unsupported workflow status. Those
changes must leave grounded decisions unchanged. Additional tests block SQL
ATTACH and manifest traversal, reject unknown structures and empty evidence, and
validate step phases, numbering and citation rules.

## Limitations

This public-sample evaluation uses local OCR and deterministic intent/planning.
No hosted model calls were made in this session. The metrics above measure the
deterministic baseline; no hidden accuracy is claimed. Warm-cache agreement
measures replay and deterministic planning only. Runtime evidence gaps are not
replaced with fabricated answers. The coverage waiver trades a fail-closed guard
for an explicit, documented completion criterion; on hidden data it can only be
wrong in the direction of an early `COMPLETE` when an unattributable copy exists,
which is exactly the residual risk reported above.

## Current full-dataset run (2026-10-25)

Command: `python code/main.py --allow-degraded --dataset dataset --output output.csv
--diagnostics evaluation_runs/final_run.json`.

- 518 rows, lexically sorted, status distribution `{"COMPLETE": 153, "INCOMPLETE": 355, "NOT_APPLICABLE": 10}`.
- 1 unresolved row (`case_63`), recorded in `degraded_cases.md`.
- Output SHA-256 `3c563f871040b1d9c225e7ed1693c420835195a2793bd1b549dc2c181772c844`.
- `submission_ready: false`; 0 OCR calls, 11 cache hits, 0 hosted model calls, 0 tokens.
- Coverage: 56 cases have an attributable account profile, 78 complete from retained
  audit records only, 19 from a fully compliant linked record set, 10 are
  `NOT_APPLICABLE`, and 1 fails closed.

`case_63` is the only remaining failure. `activity_4008` links `marketing_001` to
`kwame-mensah@proton.me`, but the eligible console screenshot `evidence_60` shows
`marketing_001` for `sj.park@naver.com`. Artifact content outranks the catalog row,
so the resource is excluded, the override is recorded in diagnostics, and no
alternative evidence for `user_09` exists in `dataset/evidence/`.

## Defects fixed across the repair sessions

| Defect | Regression proof | Measured effect |
|---|---|---|
| Negations and scoped retention exceptions reversed authorization | `test_scoped_authorization`, `test_intent_paraphrases_and_copy_prerequisites` | Sample status accuracy 23/32 to 24/32 |
| Future identity events changed earlier decisions | `test_future_identity_is_invariant`, `test_reused_email_respects_eligible_ownership_intervals` | Metamorphic invariance holds |
| Phone/name/email PII in nested retained text could be missed | `test_phone_in_retained_text_requires_redaction`, `test_nested_identifiers_and_redacted_controls` | REDACT findings emitted |
| Standalone validation accepted policy/state/citation mutations | `test_semantic_mutations_rejected_even_with_rebound_output_hash`, `test_recomputed_diagnostics_fields_cannot_be_forged` | 12 mutation families rejected |
| Reference-only tombstone screenshots were skipped | `test_reference_only_tombstone_screen_establishes_deleted_account` | `case_46` resolves |
| Backup inventory rows were skipped as if they proved nothing | `test_backup_inventory_screen_requires_restore_block` | `case_55` resolves |
| Refiner hardcoded 104 fallbacks and denominator | `test_fallback_target_count_is_not_hardcoded` | Refiner accepts the current dynamic fallback set |
| “Confirmation copy” and data-flow “copy” were treated as export prerequisites | `test_intent_paraphrases_and_copy_prerequisites` | False prerequisite fallbacks removed |
| Coverage guard failed closed with no attributable account profile | `test_retained_only_exact_key_link_permits_grounded_completion`, `test_waiver_requires_compliant_linked_records`, `test_waiver_needs_an_exact_key_not_a_name_or_position` | 97 fallbacks to 0 in this family; 5 sample status misses fixed |
| Catalog claim blocked a case even when the artifact contradicted it | `test_catalog_identity_conflict_defers_to_artifact_content`, `test_catalog_claim_kept_when_artifact_content_agrees` | `case_63` now resolves as an explicit override instead of a generic conflict |
| Root output could not be written in degraded mode | `test_allow_degraded_writes_best_effort_without_claiming_readiness` | Best-effort 518-row file with honest readiness flag |

## Reproduction

```sh
.venv/bin/python -m unittest discover -s code/tests -v
.venv/bin/python code/evaluation/coverage_experiment.py
.venv/bin/python code/main.py --allow-degraded --dataset dataset \
  --output output.csv --diagnostics evaluation_runs/final_run.json
.venv/bin/python code/validate.py --output output.csv --dataset dataset \
  --diagnostics evaluation_runs/final_run.json --allow-degraded
.venv/bin/python code/evaluation/main.py
```
