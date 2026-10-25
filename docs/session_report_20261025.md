# Session report — best-effort output, coverage waiver, artifact precedence

Date: 2026-10-25. Harness: opencode; model: `deepseek-v4.1-flash-free`.
No dataset file was modified. No hosted model call was made (0 tokens, $0).

## 1. Root `output.csv` written with `--allow-degraded`

```sh
.venv/bin/python code/main.py --allow-degraded --dataset dataset \
  --output output.csv --diagnostics evaluation_runs/final_run.json
```

- 518 data rows + header, lexically sorted, one row per `case_id`.
- Status: `COMPLETE` 153, `INCOMPLETE` 355, `NOT_APPLICABLE` 10.
- Unresolved: **1** (`case_63`), kept as `INCOMPLETE` with `steps_json=[]`.
- `submission_ready: false`, `degraded_output: "--allow-degraded"`,
  `fallback_count: 1`.
- Output SHA-256 `3c563f871040b1d9c225e7ed1693c420835195a2793bd1b549dc2c181772c844`.
- `degraded_cases.md` written at the repository root and preserved.
- Previous root artifact (SHA-256 `b2971b3c…`, 104 fallbacks) copied to
  `output_before_allow_degraded.csv` in this directory before the write.

`--allow-degraded` is a new explicit flag. It is the only way to write degraded
rows to root `output.csv`; `--review` still writes to a separate directory, and the
strict default still exits 2 and preserves prior output. The flag never marks a run
submission-ready.

## 2. Sample status misses and the always-INCOMPLETE baseline

Always-`INCOMPLETE` baseline: **22/32 (68.75%)** — 22 of 32 public samples are
`INCOMPLETE`. That baseline emits no steps, so its step precision/recall/F1 is 0.
Everything below is measured against 22/32, not 0/32.

Previous build (24/32) had eight status misses:

| Case | Expected | Produced | Root cause |
|---|---|---|---|
| `case_21` | COMPLETE | INCOMPLETE | Coverage guard: only `audit_record_3737` (RETAIN, present) is attributable; `account_6440` exists only as a 404 row with no identity key |
| `case_25` | COMPLETE | INCOMPLETE | Same guard; `account_3136` has the same unattributable 404 shape |
| `case_26` | COMPLETE | INCOMPLETE | Same guard on an already-compliant set (retained, redacted, blocked, disabled) |
| `case_27` | COMPLETE | INCOMPLETE | Same guard, same record-set shape |
| `case_28` | COMPLETE | INCOMPLETE | Same guard, same record-set shape |
| `case_01` | COMPLETE | INCOMPLETE | No eligible evidence contains any identifier of the subject; `evidence_54` has no `account_001` row and declares no scope |
| `case_02` | COMPLETE | INCOMPLETE | Same shape: the subject never appears in the eligible capture |
| `case_04` | COMPLETE | INCOMPLETE | Same shape plus `analytics_901`, whose `user_id`/`email`/`phone`/`email_hash` are all null |

Current build: **29/32 (90.62%)**, i.e. +7 over always-INCOMPLETE and +5 over the
previous build. Remaining misses are `case_01`, `case_02`, `case_04` — all three
need a record attributed to the subject by a key that does not exist in the
participant data (only the request ordinal or a resource-ID suffix would work, and
both are forbidden).

## 3. Coverage-waiver experiment

Hypothesis: when exact-key evidence (stable user reference, current/historical
email, verified email hash) links the subject only to records that already have
their required treatment, emit the grounded `VERIFY_RECORD_PRESENT` (and sibling)
steps with `COMPLETE` instead of `INCOMPLETE`/`[]`. No case-ID, timing, filename or
row-position rule participates.

`code/evaluation/coverage_experiment.py` reruns identical evidence under three
policies:

| Policy | Status | Content-step F1 | Positional-step F1 | Unmatched predicted |
|---|---:|---:|---:|---:|
| `none` (previous) | 24/32 (75.00%) | 84.21% | 65.50% | 37 |
| `retained` (retained only) | 26/32 (81.25%) | 84.88% | 65.12% | 39 |
| `compliant` (adopted) | **29/32 (90.62%)** | **88.76%** | 62.92% | 51 |

Adopted: `compliant`. Status accuracy +5 cases; content-step precision 96.64% to
96.93%, recall 74.61% to 81.87%, F1 84.21% to 88.76%.

Positional (step_no-inclusive) F1 falls 65.50% to 62.92% and is reported, not
hidden: that metric counts a correct step at a different index as both a false
positive and a false negative, and the added checks shift indices because the
unattributable account/anonymized checks preceding them are missing. The added
steps themselves are correct — content precision stays above 96% and unmatched
expected steps are unchanged at 81. Whole-case exact match is 8/32 either way.
Order is measured by the ordered-sequence (8/32) and Levenshtein (0.4315) metrics.

Guards, covered by tests: the waiver requires an exact key (a name-only or empty
identifier set disqualifies a record, and one such record disqualifies the case),
requires every decided record to be compliant, and is disabled by
`coverage_waiver='none'`.

## 4. `case_63`: observed content outranks the catalog

`activity_4008` claims `marketing_001` belongs to `kwame-mensah@proton.me`
(`user_09`). The eligible console screenshot `evidence_60` shows `marketing_001`
for `sj.park@naver.com`. The engine now treats the artifact as authoritative,
excludes the resource from the subject's ownership, and records:

```json
{"resource": "marketing_001", "artifact_category": "MARKETING_PROFILE",
 "artifact_identifiers": ["sj.park@naver.com"], "artifact_evidence": "evidence_60",
 "catalog_claim": ["sj.park@naver.com"]}
```

`dataset/evidence/` contains no other mention of `user_09`, so the case has no
grounded resource left and fails closed with
`no grounded resources before cutoff; catalog claim outranked by observed artifact
content: marketing_001 shows sj.park@naver.com`. This is a correct resolution of the
contradiction, not a resolution of the case; no steps are invented.

## 5. Verification: before/after

| Check | Before this session | After |
|---|---|---|
| Unit tests | 63/63 | **69/69** |
| Full run rows | 518 (review) | 518 (root, `--allow-degraded`) |
| `COMPLETE` / `INCOMPLETE` / `NOT_APPLICABLE` | 56 / 452 / 10 | **153 / 355 / 10** |
| Unresolved `INCOMPLETE,[]` | 98 | **1** |
| Root `output.csv` | stale 104-fallback artifact, not reproducible | current, 1 unresolved row, `submission_ready: false` |
| `validate.py --allow-degraded` | exit 0 for the 98-fallback review artifact | **exit 0** for root `output.csv` (`REVIEW ONLY`) |
| `validate.py` strict | exit 1 (`case_103: unresolved`) | exit 1 (`case_63: unresolved`) |
| `main.py` strict | exit 2, output preserved | **exit 2, output preserved** (`3c563f87…` unchanged) |
| Sample status accuracy | 24/32 (75.00%) | **29/32 (90.62%)** |
| Sample whole-case exact | 8/32 (25.00%) | 8/32 (25.00%) |
| Sample positional P / R / F1 | 75.17 / 58.03 / 65.50% | 68.71 / 58.03 / 62.92% |
| Sample content P / R / F1 | 96.64 / 74.61 / 84.21% | **96.93 / 81.87 / 88.76%** |
| Secret-shaped literals in tracked files or package | none | **none** |
| Live key material | only in gitignored root `.env` | unchanged: gitignored, excluded from `code.zip` |

Groq-key grep (`gsk_…`, `sk-…`, `AIza…` patterns; `GROQ_API_KEY`/`OPENAI_API_KEY`
references): unchanged, no credential in any tracked file, report, log, test or
archive. The only match is the gitignored root `.env`, which `package.py` cannot
include (its allowlist is `.py`/`.md`/`.txt` under `code/`, `docs/` and named root
files, and it rejects hidden paths). `.env` was not printed into the reports.

## 6. Commands

```sh
.venv/bin/python -m unittest discover -s code/tests -v
.venv/bin/python code/evaluation/coverage_experiment.py
.venv/bin/python code/main.py --allow-degraded --dataset dataset \
  --output output.csv --diagnostics evaluation_runs/final_run.json
.venv/bin/python code/validate.py --output output.csv --dataset dataset \
  --diagnostics evaluation_runs/final_run.json --allow-degraded
.venv/bin/python code/main.py --dataset dataset --output output.csv \
  --diagnostics evaluation_runs/repair_session_20261025T1100Z/strict_attempt.json   # exit 2
.venv/bin/python code/evaluation/main.py \
  --report evaluation_runs/repair_session_20261025T1100Z/sample_evaluation_final.md
grep -rn --binary-files=without-match -E "gsk_[A-Za-z0-9]{10,}|sk-[A-Za-z0-9]{20,}|AIza[0-9A-Za-z_-]{20,}" \
  --exclude-dir=.venv --exclude-dir=.git --exclude-dir=dataset .
```

## 7. Artifacts in this directory

- `output_before_allow_degraded.csv`, `degraded_cases_before.md` — preserved prior state.
- `stage_review.csv`, `stage_diagnostics.json` — first 518-case run with the new engine.
- `allow_degraded.stdout/.stderr` — root write log.
- `validate_allow_degraded.*`, `validate_strict.*` — validation output.
- `strict_attempt.json` — failed strict run diagnostics (19 MB).
- `sample_evaluation_after_coverage.md`, `sample_evaluation_final.md`,
  `sample_metrics_final.json`, `sample_predictions_final.csv` — evaluator output.
- `sample_metrics_coverage_experiment.json` — the three-policy experiment.

## 8. Readiness verdict

**Improved but still not submission-ready.** 517/518 rows are evidence-backed, the
sample now beats the always-INCOMPLETE baseline by seven cases instead of two, and
the only remaining failure is a documented ownership contradiction with no
alternative evidence. The strict gate still refuses to declare readiness, and the
root artifact is explicitly labelled best-effort.

Residual risk to state in the interview: the coverage waiver can produce an early
`COMPLETE` when an unattributable copy of the subject's data still exists. That risk
is bounded by exact-key linkage and by requiring every linked record to be
compliant, and it is measured above rather than assumed away.

## 9. Next action

1. Keep the strict gate and the dual-metric reporting.
2. Ask for clarification (or additional evidence) about how a deleted account row
   with no surviving identifier should be attributed — this affects `case_63` and
   the three remaining sample misses, and nothing else.
3. If that clarification allows a scoped-completeness rule, implement it with a
   regression test rather than by ID-suffix matching.
