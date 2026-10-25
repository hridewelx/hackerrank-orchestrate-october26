# Ghost Data Still Exists — grounded local audit

A local AI-assisted deletion-audit implementation with OCR, deterministic evidence
parsing, historical identity resolution, temporal filtering, policy planning,
strict serialization and reproducible evaluation. It never executes deletion.

**Current status: one unresolved case blocks a strict submission.**
A full 518-row run produces 153 `COMPLETE`, 355 `INCOMPLETE` and 10
`NOT_APPLICABLE` decisions, with exactly one conservative `INCOMPLETE` row whose
`steps_json=[]` (`case_63`, an ownership contradiction). The strict default refuses
to overwrite root `output.csv` while any case is unresolved; `--allow-degraded`
writes the same 518 rows explicitly as a best-effort answer and records the run as
not submission-ready. Root `output.csv` is currently that best-effort artifact.
See [evaluation](code/evaluation/evaluation_report.md) and
[evidence gaps](docs/evidence_gaps.md). No hidden accuracy is claimed.

Completed deletions are asserted from the records the subject is linked to by an
exact key (stable user reference, current or historical email, verified email hash).
When no account-profile row carries one of those keys — typically because the
deleted profile row has no identifiers left — a case is `COMPLETE` only if every
linked record already has its required treatment. `case_63` is the opposite
situation: the observed artifact names another person, so the catalog claim is
overridden and the case fails closed.

## Setup

Python 3.11+ (tested on 3.14.8), Poppler's `pdftotext`, and the pinned Python
packages are required. `python-dotenv` loads the repository-root `.env` into the
process environment, preserving existing environment values. `GROQ_API_KEY`
can be configured there; it is never printed. `.env` is ignored and excluded
from the source archive. The local baseline makes no hosted calls. The explicit
Groq refinement command uses only `openai/gpt-oss-20b` and requires a working API key
and quota. No key or raw provider error is printed.

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
```

Windows: use `.venv\Scripts\python.exe` instead. Install Poppler and put
`pdftotext` on PATH (Ubuntu/Debian: `sudo apt-get install poppler-utils`;
Fedora: `sudo dnf install poppler-utils`; macOS: `brew install poppler`).
RapidOCR ships the local ONNX weights used by this build; the first installation
requires network access. Subsequent local baseline runs need no network access; Groq refinement requires network access.

## Commands

Run from the repository root; paths are resolved relative to the source directory,
so another working directory also works:

```sh
.venv/bin/python code/main.py --no-cache
.venv/bin/python code/main.py --allow-degraded
.venv/bin/python code/evaluation/main.py
.venv/bin/python code/evaluation/coverage_experiment.py
python3 diagnose_unresolved.py . output.csv
.venv/bin/python code/evaluation/report_run.py
.venv/bin/python -m unittest discover -s code/tests -v
.venv/bin/python code/review.py
.venv/bin/python code/package.py
```

- `main.py` reads `dataset/`, audits all requests, validates every emitted step,
  and writes root `output.csv` atomically only when every case resolves. The
  default is strict: unresolved cases abort with exit 2 and preserve the prior
  output. `--review` writes an explicit degraded review artifact and can never
  overwrite root `output.csv`. `--allow-degraded` may write root `output.csv` as a
  best-effort answer; it marks the run `submission_ready: false`, keeps unresolved
  rows as `INCOMPLETE` with empty steps, and writes `degraded_cases.md` next to the
  output. Extraction failures remain fatal. Per-case diagnostics identify every
  fallback.
- `validate.py` freshly reconstructs every case from participant evidence and
  compares status, ordered steps, subject, intent, and resources. Empty
  `INCOMPLETE` steps are accepted only with `--allow-degraded`, which marks the
  result review-only. `--partial` permits an incomplete case set for development.
- `review.py` produces `evaluation_runs/review/partial_predictions.csv` plus
  `case_review.csv`, which lists every input case with explicit unresolved rows.
  **Neither is a valid 518-row submission.** Review mode cannot silently replace
  the root submission file.
- `evaluation/main.py` recomputes public sample predictions, evaluates the same fallback
  policy as the submission command, and writes all metrics directly into its Markdown report.
- `package.py` writes `code.zip` from an explicit source/documentation allowlist.
  Dataset, caches, environments, secrets and nested archives are excluded.

Useful options:

```sh
.venv/bin/python code/main.py --dataset /path/to/dataset --output /path/to/output.csv
.venv/bin/python code/review.py --no-cache
.venv/bin/python code/main.py --case-sort natural
```

Lexical case ordering is the default. `--no-cache` recomputes OCR; otherwise OCR
is cached by image bytes plus extractor/model configuration version. Structured
files are parsed once per run, not once per request. `--no-images` is an ablation
option and must never be treated as a final submission run.

## Groq refinement (unresolved fallback cases only)

Put `GROQ_API_KEY` in the uncommitted root `.env`, then run after the baseline and
public-sample evaluation:

```sh
.venv/bin/python code/refine_groq.py --max-cost-usd 1
.venv/bin/python code/validate.py --require-resolved
.venv/bin/python code/package.py
```

The command freezes the current fallback IDs and preserves every other row exactly.
No fallback count is hardcoded; the synthetic regression suite covers both 104 and
7 target cases. It uses `openai/gpt-oss-20b` hosted by Groq at
`https://api.groq.com/openai/v1/chat/completions`; no OpenAI or Gemini API is called.
`python-dotenv` loads the key; no new SDK is needed. Strict JSON schema constrains
the response. Local validation checks field types, operations/states, phases,
numbering, empty future-action citations, eligible evidence, ownership, policy,
replicas and full known-resource coverage. Missing account coverage cannot prove
COMPLETE. Unsupported model answers remain explicitly unresolved.

Usage records every attempt and each response's token counts. Estimated cost
uses published Groq list prices; free-tier billing may differ. Completed responses
and prompt hashes are cached under ignored `evaluation_runs/groq_refinement/`.
The run stops before its estimated/reserved cost exceeds the cap. Temporary 429
rate limits retry at most five times per case using Retry-After (up to 120 seconds).
Other provider failures require explicit `--retry-provider-errors`; completed
responses are never resent. An interrupted in-flight request requires review.

Do not rerun `main.py` after refinement unless restoring the local baseline.
Changed evidence or output causes a safe refusal to overwrite. Public samples
are evaluated locally and are not sent to Groq. `--require-resolved` rejects any remaining empty INCOMPLETE fallback. The evaluation report distinguishes
structural validity from evidence-backed resolution and measured sample accuracy.

## Architecture and tradeoffs

1. **Ingest** manifest-referenced evidence only. JSON structures, six operational
   log envelopes, SQL tables, text handovers and PDFs become typed observations.
   Local PP-OCRv6 detects/recognizes image text with bounding boxes and confidence.
2. **Link identities** using trim/lowercase current and all historical emails, supplied
   hashes, stable user references and explicit catalog/trace links. Identity
   knowledge, history events and snapshot updates are gated at `audit_at`, and
   alias ownership intervals are checked at observation time. Expand every
   history edge for the resolved user_id, including raw phone aliases; phones
   and names alone cannot establish ownership. Email changes after `requested_at`
   produce diagnostic warnings without blocking a case. SHA-256 is enabled only
   after checking every supplied current email/hash pair. No matching on names,
   phone numbers, numeric ID suffixes or evidence filenames.
3. **Investigate** eligible identifier hits, catalog links and resource histories.
   The fixed read-only sequence has finite bounds determined by the manifest and
   resource set. It is not represented as an autonomous language-model tool loop.
4. **Reconcile** actual observations separately from write-operation claims.
   Capture time and observation time must both precede the case cutoff. Each
   replica's latest observation remains independently relevant. Missing rows in
   partial bundles do not prove absence.
5. **Apply policy** from `deletion_rules.csv`: delete, redact, anonymize, retain,
   or preserve the stable reference in a tombstone. Active flows and unsafe
   restores are treated separately from records.
6. **Plan** permitted steps in the explicit operation-table order. Findings and
   complete-case checks cite sources; future actions/checks have empty citations.

This favors an auditable small pipeline over a multi-agent framework. Local OCR
adds measurable evidence extraction without API spend. The local intent baseline
uses bounded multilingual rules. The targeted Groq stage classifies
intent and proposes steps for the current unresolved fallbacks only; it is not used to
silently manufacture evidence or change the already resolved cases.

## Evidence and evaluation limits

The report distinguishes parser defects that were fixed from unresolved evidence
associations and conflicting public expectations. Some absent/anonymized resources
have no supplied identity link, and some expected records occur only in later
captures. These are not filled using sample answers. Partial output may still
miss anonymous resources or phone-only links; 517 emitted decisions, one of them an
unproven fallback, do not mean 517 independently verified correct answers.

The isolated regression suite currently has 69 passing tests covering historical
identity, decoys, multilingual intent, prerequisites, cutoff leakage, replica
drift, recreation, retention, tombstones, backup inventory screens, catalog-vs-artifact
ownership, coverage waivers, hostile SQL, path traversal and input metamorphisms.
Public sample evaluation is development evaluation: 29/32 status matches and 8/32
exact sequences at this build, with all fallback cases included in the denominator.

## Artifacts and interview

- `output.csv`: current best-effort 518-row artifact from `--allow-degraded`,
  153 `COMPLETE` / 355 `INCOMPLETE` / 10 `NOT_APPLICABLE`, one unresolved row
  (`case_63`); **not** submission-ready.
- `code.zip`: runnable source archive and reports.
- `code/evaluation/evaluation_report.md`: measured metrics and custom scenarios.
- `code/evaluation/usage_report.md`: current review OCR counts and historical token usage recomputed from actual API responses.
- `degraded_cases.md`: current unresolved list (one case). Earlier 98- and
  104-case lists are preserved under `evaluation_runs/repair_session_*/`.
- `diagnose_unresolved.py`: participant-provided read-only diagnostic, preserved unchanged.
- `log.txt`: authentic append-only coding-session summary; submit separately.
- `docs/trace_collection.md`: collect `agent-trace.zip` after closing active sessions.
- `docs/interview.md`: architecture, failures, costs and discussion questions.

The supplied diagnostic reports 0 formatting/ordering problems for the current
output but counts one empty fallback, so this is not full semantic readiness. No
hosted calls were made in this session. Earlier Groq usage is reported separately.
The session report is tracked at `docs/session_report_20261025.md`; the full run
logs and diagnostics are ignored and live under `evaluation_runs/repair_session_*/`.

The archive includes reports at both `code/evaluation/` and `evaluation/` to
satisfy the two documented layouts. The dataset remains external.
