# Interview preparation grounded in this implementation

## Explain the architecture

“I normalize participant evidence into records with source IDs, locators, capture
and observation times. I connect identities through strong identifiers and
historical changes, inspect resource histories, keep replicas separate, and apply
the supplied policy. A deterministic planner emits only permitted steps. Local
OCR reads screenshots. Unknown evidence and missing ownership links fail visibly.”

Do not claim a fully working 518-case submission, hidden-test accuracy, a language
model investigation loop, or perfect OCR. Those have not been demonstrated.

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

No paid API calls. RapidOCR 3.10.0 uses local PP-OCRv6 detector/recognizer and a local
orientation classifier. A cold full-dataset review calls the OCR pipeline once for
each of 11 images. Structured evidence is parsed once per run. No LLM token meter
exists in this pipeline because no LLM is called. Electricity and hardware time
are not claimed to be zero-cost merely because API cost is zero.

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
