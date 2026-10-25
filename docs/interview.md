# Interview preparation grounded in this implementation

## Explain the architecture

“I normalize participant evidence into records with source IDs, locators, capture
and observation times. I connect identities through strong identifiers and
all historical changes, inspect resource histories, keep replicas separate, and apply
the supplied policy. A deterministic planner emits only permitted steps. Local
OCR reads screenshots. Unknown evidence and missing ownership links fail visibly.”

The pipeline now resolves 517 of 518 rows without a fallback. One case (`case_63`)
is a conservative INCOMPLETE/empty-step fallback after the catalog claim is
overridden by the observed artifact, not a proven finding. The documented command
therefore writes that file in degraded mode with a warning banner and
`submission_ready: false`; `--strict` is the fail-closed gate that refuses to write.
Do not claim all cases are solved, hidden-test accuracy, a language-model
investigation loop, or perfect OCR.

An independent audit (`code/audit_complete.py`) re-derives every `COMPLETE` row from
identity knowledge and raw evidence without using the planner: it found 0
unaccounted subject-linked records and 0 state conflicts across 153 completions, and
a negative control confirms it catches a deliberately removed verification step.

## Difficult actual case

For sample case_05, the primary database does not contain account_005, but
`evidence_54` contains the profile and identifying values in its failover table.
The email/stable user reference links the row to the request. USER_PROFILE requires
deletion, so the output reports the remaining record, plans deletion, then verifies
absence. A successful deletion workflow cannot discharge the replica.

## Real failures and fixes

- Condition parsing confused a contact-information offer with conditional deletion.
  Restricting the detection removed 64 initial failures.
- Escaped cloud-log envelopes lost their final value quote, misreading row counts.
  Proper envelope normalization fixed this parser defect.
- A marketing-only opt-out matched broad deletion words. Scope-specific rejection
  now has a regression test.
- Broad snapshot omissions implied missing retained records. Scope restriction
  prevents a partial batch from masquerading as a global inventory.
- A fail-closed coverage guard produced 97 empty answers even when every linked
  record was already compliant. Completion is now asserted from exact-key-linked,
  already-treated records, with the waiver recorded in diagnostics.
- A catalog link that contradicted the artifact it pointed at blocked a whole case.
  Observed artifact content now outranks the catalog row, and the override is
  recorded instead of being hidden.
- Remaining failures include unlinked erased resources. This is documented rather
  than solved through numeric suffix guessing or sample-label lookup.
- The sample gate is reported with two step metrics. Positional F1 includes
  `step_no`; content F1 excludes it. The coverage waiver improved status accuracy
  (24/32 to 29/32) and content F1 (84.21% to 88.76%) while positional F1 fell
  (65.50% to 62.92%), because missing earlier steps shift every later index.

## Measured choices and costs

The baseline used no hosted API. RapidOCR 3.10.0 uses local PP-OCRv6 detection,
recognition and orientation classification; the historical cold full run processed
11 images, and the current review reused 11 cached OCR results.
Groq refinement records attempts, reported input/output/cached tokens and estimated
cost in `code/evaluation/usage_report.md`. Provider failures without usage are
reported separately, not assigned invented token counts. Earlier OpenAI attempts
failed and contributed no output. Electricity and hardware costs are not estimated.

## Participant decisions actually made

The participant authorized implementation and milestone pushes, chose a GitHub
fork, then changed the earlier OpenAI preference to local/free execution. Do not
claim they designed the policy engine or chose specific parser fixes.

## Production concerns

Implemented: explicit parser failures, per-case timing, source locators, resource
coverage warnings, cutoff checks, local OCR cache, strict step validation.
Not implemented: live deletion execution, full schema-drift monitoring service,
model uncertainty calibration, human-review UI, policy-authoring system, continuous
replica monitoring. Those would be needed before real data deletion operations.

## Mock interview, one question at a time

Start with: “A deletion job reports SUCCESS, the primary is clean, but a failover
snapshot still contains the profile. What does your implementation conclude, and
which evidence controls that conclusion?”

Then discuss historical linkage, post-cutoff evidence, retention/tombstones,
missing coverage, metric denominators, local OCR limitations, and the participant's
actual decisions. Correct answers against the source; do not script invented
ownership or results.

## Targeted Groq integration

Only the current unresolved fallback requests are eligible for `openai/gpt-oss-20b`
on Groq. All other rows are preserved. The target count is derived from diagnostics,
not hardcoded. Eligible evidence packets, strict JSON schema, local evidence
validation, prompt hashes, token/cost records and resumable rate-limit handling
support reproducibility. Missing evidence remains unresolved; refer to the
evaluation report for the actual accepted/rejected counts. No new paid calls were
made in the 2026-10-25 repair session.
