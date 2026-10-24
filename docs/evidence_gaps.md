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
  from a row that is not in the snapshot without another link.
- Public case_21 expects account_6440 and analytics_5335. evidence_92 contains a
  null-profile lookup for the account and a sanitized analytics row, but neither
  carries the subject identifier needed to associate it with the request. The
  retained audit record is linked. This differs from proving all required copies.
- Public case_24 expects retained audit_record_7095 as a future verification. Its
  record is in a bundle captured September 17, after the September 15 audit cutoff.
  The eligible evidence_92 export does not contain that security record. The
  implementation cannot discover it by reading future evidence for the case.
- Public case_07's expected output omits object_19; activity_4007 explicitly links
  that object to the subject, and evidence_46 shows the named attachment. Current
  implementation includes that additional object, lowering exact sample matching.
- Evaluation case_55 has a linked backup archive displayed in a console, but the
  screen does not establish whether this subject's restore access is blocked.
  Merely seeing a stored archive is insufficient to assert an active restore path.

The catalog and screenshot can also disagree on ownership (for example a marketing
resource linked to one subject while the screen displays another). The implementation now stops on an artifact/catalog ownership conflict. A catalog
link is not assumed to be infallible simply because its operation succeeded.

## Current full-dataset review

Attempted 518; emitted 414; unresolved 104.

| Case | Diagnostic |
|---|---|
| case_103 | Cannot prove completion: No grounded account resource: cannot prove account deletion coverage |
| case_107 | Cannot prove completion: No grounded account resource: cannot prove account deletion coverage |
| case_108 | Cannot prove completion: No grounded account resource: cannot prove account deletion coverage |
| case_111 | Cannot prove completion: No grounded account resource: cannot prove account deletion coverage |
| case_112 | Cannot prove completion: No grounded account resource: cannot prove account deletion coverage |
| case_126 | Cannot prove completion: No grounded account resource: cannot prove account deletion coverage |
| case_127 | Cannot prove completion: No grounded account resource: cannot prove account deletion coverage |
| case_150 | Cannot prove completion: No grounded account resource: cannot prove account deletion coverage |
| case_151 | Cannot prove completion: No grounded account resource: cannot prove account deletion coverage |
| case_152 | Cannot prove completion: No grounded account resource: cannot prove account deletion coverage |
| case_155 | Cannot prove completion: No grounded account resource: cannot prove account deletion coverage |
| case_157 | Cannot prove completion: No grounded account resource: cannot prove account deletion coverage |
| case_162 | Cannot prove completion: No grounded account resource: cannot prove account deletion coverage |
| case_175 | Cannot prove completion: No grounded account resource: cannot prove account deletion coverage |
| case_178 | Cannot prove completion: No grounded account resource: cannot prove account deletion coverage |
| case_183 | Cannot prove completion: No grounded account resource: cannot prove account deletion coverage |
| case_190 | Cannot prove completion: No grounded account resource: cannot prove account deletion coverage |
| case_191 | Cannot prove completion: No grounded account resource: cannot prove account deletion coverage |
| case_204 | Cannot prove completion: No grounded account resource: cannot prove account deletion coverage |
| case_206 | Cannot prove completion: No grounded account resource: cannot prove account deletion coverage |
| case_213 | Cannot prove completion: No grounded account resource: cannot prove account deletion coverage |
| case_215 | Cannot prove completion: No grounded account resource: cannot prove account deletion coverage |
| case_218 | Cannot prove completion: No grounded account resource: cannot prove account deletion coverage |
| case_219 | Cannot prove completion: No grounded account resource: cannot prove account deletion coverage |
| case_221 | Cannot prove completion: No grounded account resource: cannot prove account deletion coverage |
| case_225 | Cannot prove completion: No grounded account resource: cannot prove account deletion coverage |
| case_226 | Cannot prove completion: No grounded account resource: cannot prove account deletion coverage |
| case_231 | Cannot prove completion: No grounded account resource: cannot prove account deletion coverage |
| case_243 | Cannot prove completion: No grounded account resource: cannot prove account deletion coverage |
| case_244 | Cannot prove completion: No grounded account resource: cannot prove account deletion coverage |
| case_253 | Cannot prove completion: No grounded account resource: cannot prove account deletion coverage |
| case_257 | Cannot prove completion: No grounded account resource: cannot prove account deletion coverage |
| case_260 | Cannot prove completion: No grounded account resource: cannot prove account deletion coverage |
| case_274 | Cannot prove completion: No grounded account resource: cannot prove account deletion coverage |
| case_276 | Cannot prove completion: No grounded account resource: cannot prove account deletion coverage |
| case_277 | Cannot prove completion: No grounded account resource: cannot prove account deletion coverage |
| case_294 | Cannot prove completion: No grounded account resource: cannot prove account deletion coverage |
| case_295 | Cannot prove completion: No grounded account resource: cannot prove account deletion coverage |
| case_297 | Cannot prove completion: No grounded account resource: cannot prove account deletion coverage |
| case_299 | Cannot prove completion: No grounded account resource: cannot prove account deletion coverage |
| case_304 | Cannot prove completion: No grounded account resource: cannot prove account deletion coverage |
| case_308 | Cannot prove completion: No grounded account resource: cannot prove account deletion coverage |
| case_309 | Cannot prove completion: No grounded account resource: cannot prove account deletion coverage |
| case_313 | Cannot prove completion: No grounded account resource: cannot prove account deletion coverage |
| case_314 | Cannot prove completion: No grounded account resource: cannot prove account deletion coverage |
| case_319 | Cannot prove completion: No grounded account resource: cannot prove account deletion coverage |
| case_322 | Cannot prove completion: No grounded account resource: cannot prove account deletion coverage |
| case_335 | Cannot prove completion: No grounded account resource: cannot prove account deletion coverage |
| case_336 | Cannot prove completion: No grounded account resource: cannot prove account deletion coverage |
| case_339 | Cannot prove completion: No grounded account resource: cannot prove account deletion coverage |
| case_343 | Cannot prove completion: No grounded account resource: cannot prove account deletion coverage |
| case_345 | Cannot prove completion: No grounded account resource: cannot prove account deletion coverage |
| case_346 | Cannot prove completion: No grounded account resource: cannot prove account deletion coverage |
| case_351 | Cannot prove completion: No grounded account resource: cannot prove account deletion coverage |
| case_354 | Cannot prove completion: No grounded account resource: cannot prove account deletion coverage |
| case_362 | Cannot prove completion: No grounded account resource: cannot prove account deletion coverage |
| case_393 | Cannot prove completion: No grounded account resource: cannot prove account deletion coverage |
| case_395 | Cannot prove completion: No grounded account resource: cannot prove account deletion coverage |
| case_398 | Cannot prove completion: No grounded account resource: cannot prove account deletion coverage |
| case_403 | Cannot prove completion: No grounded account resource: cannot prove account deletion coverage |
| case_408 | Cannot prove completion: No grounded account resource: cannot prove account deletion coverage |
| case_409 | Cannot prove completion: No grounded account resource: cannot prove account deletion coverage |
| case_411 | Cannot prove completion: No grounded account resource: cannot prove account deletion coverage |
| case_412 | Cannot prove completion: No grounded account resource: cannot prove account deletion coverage |
| case_423 | Cannot prove completion: No grounded account resource: cannot prove account deletion coverage |
| case_424 | Cannot prove completion: No grounded account resource: cannot prove account deletion coverage |
| case_427 | Cannot prove completion: No grounded account resource: cannot prove account deletion coverage |
| case_430 | Cannot prove completion: No grounded account resource: cannot prove account deletion coverage |
| case_448 | Cannot prove completion: No grounded account resource: cannot prove account deletion coverage |
| case_45 | Cannot prove completion: No grounded account resource: cannot prove account deletion coverage |
| case_452 | Cannot prove completion: No grounded account resource: cannot prove account deletion coverage |
| case_456 | Cannot prove completion: No grounded account resource: cannot prove account deletion coverage |
| case_457 | Cannot prove completion: No grounded account resource: cannot prove account deletion coverage |
| case_458 | Cannot prove completion: No grounded account resource: cannot prove account deletion coverage |
| case_46 | Linked resources lack state observations: ['tombstone_17'] |
| case_462 | Cannot prove completion: No grounded account resource: cannot prove account deletion coverage |
| case_463 | Cannot prove completion: No grounded account resource: cannot prove account deletion coverage |
| case_464 | Cannot prove completion: No grounded account resource: cannot prove account deletion coverage |
| case_467 | Cannot prove completion: No grounded account resource: cannot prove account deletion coverage |
| case_470 | Cannot prove completion: No grounded account resource: cannot prove account deletion coverage |
| case_480 | Cannot prove completion: No grounded account resource: cannot prove account deletion coverage |
| case_493 | Cannot prove completion: No grounded account resource: cannot prove account deletion coverage |
| case_494 | Cannot prove completion: No grounded account resource: cannot prove account deletion coverage |
| case_497 | Cannot prove completion: No grounded account resource: cannot prove account deletion coverage |
| case_502 | Cannot prove completion: No grounded account resource: cannot prove account deletion coverage |
| case_506 | Cannot prove completion: No grounded account resource: cannot prove account deletion coverage |
| case_512 | Cannot prove completion: No grounded account resource: cannot prove account deletion coverage |
| case_524 | Cannot prove completion: No grounded account resource: cannot prove account deletion coverage |
| case_530 | Cannot prove completion: No grounded account resource: cannot prove account deletion coverage |
| case_532 | Cannot prove completion: No grounded account resource: cannot prove account deletion coverage |
| case_543 | Cannot prove completion: No grounded account resource: cannot prove account deletion coverage |
| case_545 | Cannot prove completion: No grounded account resource: cannot prove account deletion coverage |
| case_547 | Cannot prove completion: No grounded account resource: cannot prove account deletion coverage |
| case_549 | Cannot prove completion: No grounded account resource: cannot prove account deletion coverage |
| case_55 | case_55: no grounded resources before cutoff |
| case_57 | Cannot prove completion: No grounded account resource: cannot prove account deletion coverage |
| case_58 | Cannot prove completion: No grounded account resource: cannot prove account deletion coverage |
| case_59 | Cannot prove completion: No grounded account resource: cannot prove account deletion coverage |
| case_60 | Cannot prove completion: No grounded account resource: cannot prove account deletion coverage |
| case_63 | Catalog ownership conflicts with artifact identifiers for marketing_001 |
| case_64 | Cannot prove completion: No grounded account resource: cannot prove account deletion coverage |
| case_69 | Cannot prove completion: No grounded account resource: cannot prove account deletion coverage |
| case_70 | Cannot prove completion: No grounded account resource: cannot prove account deletion coverage |
| case_97 | Cannot prove completion: No grounded account resource: cannot prove account deletion coverage |

The normal CLI deliberately does not produce output.csv for this unresolved dataset. The separate case_review.csv includes all 518 requests with explicit unresolved outcomes.
