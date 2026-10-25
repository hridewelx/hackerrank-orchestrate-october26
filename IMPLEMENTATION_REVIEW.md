# Implementation review — 2026-10-25

**Verdict: the current submission is reproducible, but it is not fully correct or semantically submission-ready.** This review executed the existing tests, a fresh full-dataset run with OCR cache reads disabled, public-sample evaluation, independent counterexamples, strict validation, and the extracted source archive. No hosted API calls were made. Source code, supplied data, output.csv, code.zip, and existing evaluation reports were not changed by this review.

## Verified results

| Check | Result |
|---|---|
| Existing unit tests | 44/44 pass |
| Full-dataset output | 518 unique rows; 104 unresolved fallbacks |
| Fresh output vs. submitted output | Byte-identical |
| Fresh ingestion | 94 evidence files, 3,025 observations, 11 fresh OCR calls |
| Public-sample status accuracy | 23/32, 71.875% |
| Public-sample whole-case and sequence exact match | 8/32, 25% |
| Exact-step precision / recall / F1 | 77.86% / 56.48% / 65.47% |
| COMPLETE sample classification | 1/10 correct; 9 labelled INCOMPLETE |
| Strict submission validation | Fails: 104 unresolved fallback rows |
| code.zip | 28 entries; readable; matches working-tree files; required reports/dependencies included |
| Extracted archive execution | Exit 0; reproduces output byte-for-byte using existing installed dependencies and the external supplied dataset |
| agent-trace.zip | Not present; final trace collection remains outstanding |

The archive check reused the installed Python environment and the fresh OCR cache. It verifies source packaging and execution, not a new dependency installation on another operating system. Public samples are development data, not hidden-test accuracy.

## Findings, ordered by impact

### P1 — Default output substitutes unsupported verdicts for unresolved cases

Location: `code/main.py:40–46`; fallback bypass in `code/validate.py:30–33`.

The default CLI catches an AuditError and emits `INCOMPLETE,[]`. There are 104 such rows (20.1% of the dataset), so these cases have neither evidence-backed findings nor the required remediation and verification plans. The normal validator explicitly exempts these rows from the step contract. `code/validate.py --require-resolved` correctly rejects the current submission.

The fresh run reproduces the documented causes: 101 cases lack grounded account coverage; one lacks a linked tombstone observation; one has no eligible grounded resources; one has a catalog/artifact ownership conflict. A missing resource also discards otherwise supported findings: public case_17 contains a grounded active backup observation but becomes an empty fallback because tombstone_17 has no eligible state observation.

Fix direction: retain unresolved diagnostics and supported findings for investigation; repair evidence extraction, linkage, and coverage. Require semantic resolution before declaring a final submission valid. Do not force COMPLETE or fabricate steps to remove fallbacks. Sample mismatches are not all proven parser bugs: some expected resources lack usable ownership links, and those ambiguities need evidence or official clarification.

### P1 — Authorization regexes reverse explicit user intent

Location: `code/ghost_audit/intent.py:16–26`.

Reproduced directly through classify():

| Request | Expected authorization | Actual |
|---|---|---|
| Please don't remove my account. | False | True |
| I am not requesting deletion of my account. | False | True |
| Delete my account, but do not delete the invoices you must retain. | True, with retained invoices | False |

The negation expression misses common negative constructions, while the broad positive deletion pattern matches their words. Conversely, a negated subrequest cancels the entire request. This can generate deletion plans without authorization or suppress an authorized deletion. The baseline supplies these decisions directly; only fallback cases reach the optional model stage.

Fix direction: reason about negation and its scope, distinguish retained-resource exceptions from denial of account deletion, and add these counterexamples to regression coverage.

### P1 — Future identity events affect decisions before audit_at

Location: `code/ghost_audit/identity.py:30–39,56–66`.

IdentityIndex.at receives a cutoff but deliberately ignores it. An isolated fixture initially returns COMPLETE. Adding a July 1 email-change event linking a new alias causes the same June 1 audit to become INCOMPLETE by associating an older search record with that future alias. No eligible evidence record changed. This violates the supplied rule that later information must not change the audit answer.

The existing test `test_identity_after_request_and_audit_warns_but_does_not_gate` endorses this behavior, so passing it is not evidence of temporal correctness. The evaluation report says the current supplied data has no relevant identity events beyond its cutoffs; the reproduction establishes a real implementation defect, not a measured count of affected current rows.

Fix direction: make identity knowledge and attribution time-aware, including history events and snapshot update times. Keep historical aliases supported by eligible evidence; do not simply discard all history. Adding only future identity information should leave a past decision unchanged.

### P1 — Exposed phone numbers in support text are certified as redacted

Location: `code/ghost_audit/ingest.py:36–42,51–52`.

has_pii checks named identifier fields and email-like tokens in message text. It does not detect a phone number in the message body. With a known subject, a confirmed absent account, cleared structured contact fields, and the support message “My phone number is +1 202 555 0100. Please call me.”, the system returns COMPLETE and emits VERIFY_RECORD_REDACTED for the support record. The number matches the synthetic subject's identity.

Fix direction: inspect free-text content against the subject's grounded identifiers and traverse nested lists as well as dictionaries. Keep ownership attribution separate from detecting exposed identifiers in an already linked record. Add phone/name/hash and nested-content tests where policy requires their removal.

### P2 — Standalone validation does not verify state or policy support

Location: `code/validate.py:37–42`.

The validator checks the cited resource/system/evidence tuple, times, and locator, but not whether the cited observation supports the operation/state or whether remediation matches the required action. In an isolated fixture, replacing a USER_PROFILE DELETE plan with REPORT_EXPOSED_PII → REDACT_RECORD → VERIFY_RECORD_REDACTED still passes validation against the unchanged diagnostics and DELETE policy.

Fix direction: validate each finding against the established state and category policy, and verify the complete required remediation/verification set. Bind diagnostics to the relevant dataset/output version. The existing check is useful structural validation, but it cannot establish semantic correctness.

## Model refinement and remaining prompt requirements

The historical Groq ledger contains 104 rejected responses and 103 provider-error attempts, with zero accepted replacements. No new calls were needed to verify this.

The current refiner reads the baseline's observations and validates proposed steps against a plan recomputed from exactly those observations (`code/ghost_audit/groq_refiner.py:173–202`). Although document text is sent to the model, there is no grounded extraction path that converts newly discovered document facts into observations accepted by the validator. Consequently, the present refinement cannot repair the missing account coverage responsible for most unresolved cases. Add provenance-checked extraction or investigation tools before spending on more identical review calls; preserve the rejection of unsupported answers.

Other requested capabilities are limited or absent:

- The final run uses local OCR and deterministic reasoning; it has no adaptive language-model tool loop. The README acknowledges this accurately.
- Image extraction uses fixed screen regions. PDFs without a text layer raise an error; PDF OCR fallback is not implemented.
- Policy handling largely maps category to action; only selected retention/tombstone conditions are checked explicitly. General semantic condition interpretation is absent.
- Independent uncached hosted-model stability has not been measured. The successful reruns establish local reproducibility, not hosted-model determinism.
- Interview preparation exists as documentation; an interactive mock interview is a separate remaining activity.
- Trace collection should occur after sessions finish, as required by agent_trace_instructions.md.

## Reproduction artifacts

Review outputs are isolated under `/tmp/orchestrate-review-dq_fhe4k/`:

- `summary.json`: full run and sample metrics.
- `full_run.json`, `sample_run.json`, `sample_metrics.json`: detailed results.
- `reproduce_review.py`, `reproductions.json`: independent counterexamples and actual outcomes.
- `archive/`: extracted code.zip and its reproduced output.

Run the counterexamples from this checkout with:

```sh
.venv/bin/python /tmp/orchestrate-review-dq_fhe4k/reproduce_review.py
```

Temporary artifacts may be removed by the operating system. This report preserves the cases and outcomes. Address authorization, temporal attribution, PII detection, and evidence coverage before treating the passing unit suite or archive reproducibility as approval to submit.

---

## Follow-up repair results — 2026-10-25 (opencode / DeepSeek V4.1 Flash Free)

This section records changes made after the independent review above. Original
findings are preserved; nothing in the dataset was edited.

### Fixed and regression-proven

| Original finding | Repair | Regression proof |
|---|---|---|
| P1 authorization regexes reversed negations and retention exceptions | Clause-scoped negatives, retention exceptions, advice/hypothetical detection, access/update/marketing classification, confirmation-copy exclusion, and request-aware export prerequisites | `test_scoped_authorization`, `test_intent_paraphrases_and_copy_prerequisites`, `test_conditional_authorization_requires_proof`, `test_multilingual_and_negated_intents` |
| P1 future identity events changed past decisions | Identity snapshots and history events are cutoff-gated; alias ownership intervals are checked at observation time | `test_future_identity_is_invariant`, `test_reused_email_respects_eligible_ownership_intervals`, `test_future_snapshot_alone_does_not_establish_past_identity` |
| P1 nested/phone PII could be missed | Nested text and phone matching now drive `REDACT`/anonymize findings without treating query metadata as stored PII | `test_phone_in_retained_text_requires_redaction`, `test_nested_identifiers_and_redacted_controls`, `test_query_metadata_is_not_stored_pii` |
| P2 standalone validation did not verify policy/state support | Validator now reconstructs each case and compares status, ordered steps, subject, intent, resources, dataset/request/behavior/output digests | `test_semantic_mutations_rejected_even_with_rebound_output_hash` (12 mutation families), `test_recomputed_diagnostics_fields_cannot_be_forged`, `test_stale_diagnostics_and_future_citations_rejected` |
| Remaining public `case_17` tombstone fallback | Reference-only tombstone screenshots now create an `ACCOUNT_TOMBSTONE`/`REDACTED` observation; visible direct identifiers still require redaction | `test_reference_only_tombstone_screen_establishes_deleted_account`, `test_reference_screen_with_direct_identifier_requires_redaction` |
| Evaluation `case_55` backup console gap | Backup inventory rows now create an account-linked `BACKUP_ARCHIVE` observation; an unblocked archive is a restore path requiring `BLOCK_RESTORE` | `test_backup_inventory_screen_requires_restore_block` |
| Refiner hardcoded 104 fallbacks | Target count is derived from diagnostics; diagnostics/error-list disagreement is rejected | `test_fallback_target_count_is_not_hardcoded`, `test_only_fallback_targets_called_and_remaining_rows_preserved` |

### Current measured state

- Tests: **63/63 pass** (was 44/44 at review baseline).
- Public sample: **24/32 status (75.00%)**, **8/32 whole-case exact (25.00%)**,
  step precision **75.17%**, recall **58.03%**, F1 **65.50%**
  (baseline 23/32, 8/32, 77.86%, 56.48%, 65.47%).
- Full review: **518 rows**, 56 `COMPLETE`, 452 `INCOMPLETE` (98 of them empty
  fallbacks), 10 `NOT_APPLICABLE`.
- Unresolved: **98** (was 104). Causes: 78 cases have only an eligible retained
  security-audit record; 19 have support/backup/flow evidence but no
  account/profile evidence; 1 (`case_63`) has a catalog/screenshot ownership
  conflict for `marketing_001`.
- No hosted API calls were made in this repair session.

### Verdict

The reviewed defects are fixed and covered by regression tests. The implementation
is more robust and one previously unresolved evaluation case (`case_55`) now has an
evidence-backed remediation plan. It is still **not submission-ready**: 98 cases
lack enough participant-visible evidence to prove account coverage or to resolve
ownership, and the strict command correctly refuses to overwrite the preserved root
`output.csv`. The remaining gaps are dataset-evidence/ownership ambiguities, not
authorization, temporal, PII, or validator defects. Do not force them to `COMPLETE`
or invent findings; they need additional participant evidence or official
clarification.


---

## Follow-up — coverage waiver, artifact precedence, best-effort output (2026-10-25, session 2)

Same harness/model (`opencode`, `deepseek-v4.1-flash-free`). Dataset unchanged; no
hosted calls.

### Changes

| Change | Rationale | Regression proof |
|---|---|---|
| Coverage waiver for exact-key-linked, fully compliant record sets | The old guard returned 97 empty answers even when every attributable record already had its required treatment | `test_retained_only_exact_key_link_permits_grounded_completion`, `test_waiver_requires_compliant_linked_records`, `test_waiver_needs_an_exact_key_not_a_name_or_position` |
| Observed artifact content outranks a catalog identity claim | `evidence_60` shows `marketing_001` belongs to `sj.park@naver.com`, not to the catalog's claim; the override is recorded instead of aborting the case | `test_catalog_identity_conflict_defers_to_artifact_content`, `test_catalog_claim_kept_when_artifact_content_agrees` |
| `--allow-degraded` writes the best 518-row answer to root, never claiming readiness | Requested explicit path for a best-effort submission artifact | `test_allow_degraded_writes_best_effort_without_claiming_readiness` |
| Content-step metric added next to the positional metric | `step_no` in the matched tuple makes a correct step at a different index unmatchable | Evaluator reports both for every run |

### Current measured state

- Tests: **69/69 pass**.
- Public sample: **29/32 status (90.62%)**, 8/32 whole-case exact, positional
  P/R/F1 **68.71/58.03/62.92%**, content P/R/F1 **96.93/81.87/88.76%**.
  Always-`INCOMPLETE` baseline is 22/32; the previous build was 24/32.
- Full run (`--allow-degraded`): 518 rows, **153 `COMPLETE`**, 355 `INCOMPLETE`,
  10 `NOT_APPLICABLE`, **1 unresolved** (`case_63`), output SHA-256
  `3c563f871040b1d9c225e7ed1693c420835195a2793bd1b549dc2c181772c844`,
  `submission_ready: false`.
- Strict run still exits 2 and preserves the root artifact; strict validation still
  refuses `case_63`.

### Verdict

Meaningfully closer, still not submission-ready. One documented ownership
contradiction remains, and the waiver's residual risk is an early `COMPLETE` when an
unattributable copy exists. Full detail:
`docs/session_report_20261025.md`.
