# Interview preparation grounded in this implementation

## Explain the architecture

“I normalize participant evidence into records with source IDs, locators, capture
and observation times. I connect identities through strong identifiers and
historical changes, inspect resource histories, keep replicas separate, and apply
the supplied policy. A deterministic planner emits only permitted steps. Local
OCR reads screenshots. Unknown evidence and missing ownership links fail visibly.”

The pipeline emits all 518 rows, but 104 are conservative INCOMPLETE/empty-step
fallbacks, not proven findings. Do not claim all cases are solved, hidden-test
accuracy, a language-model investigation loop, or perfect OCR.

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
- Remaining failures include unlinked erased resources. This is documented rather
  than solved through numeric suffix guessing or sample-label lookup.

## Measured choices and costs

The baseline used no hosted API. RapidOCR 3.10.0 uses local PP-OCRv6 detection,
recognition and orientation classification; the cold full run processed 11 images.
The OpenAI refinement now records reported tokens and costs, but both live attempts
returned HTTP 429 without token usage. Known metered usage is zero; unreported
usage and billing are unknown. Electricity and hardware costs are not estimated.

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

## Targeted OpenAI integration

Only the original 104 fallback requests are eligible for gpt-4o-mini. The other
414 rows are preserved. Eligible evidence packets, structured responses, prompt
hashes and token/cost records support reproducibility. The first two live API
attempts returned HTTP 429, so there are no successful model completions and no
accuracy improvement to claim. Retry after provider access/quota is available.
