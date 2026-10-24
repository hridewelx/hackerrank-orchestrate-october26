# Ghost Data Still Exists — grounded local audit

A local AI-assisted deletion-audit implementation with OCR, deterministic evidence
parsing, historical identity resolution, temporal filtering, policy planning,
strict serialization and reproducible evaluation. It never executes deletion.

**Current status: development build, not submission-ready.** The supplied evidence
permits this implementation to produce decisions for 414 of 518 evaluation
requests; 104 require review. The normal run fails explicitly and does not write
an incomplete `output.csv`. See [evaluation](code/evaluation/evaluation_report.md)
and [evidence gaps](docs/evidence_gaps.md). No hidden accuracy is claimed.

## Setup

Python 3.11+ (tested on 3.14.8), Poppler's `pdftotext`, and the pinned Python
packages are required. No API credentials or paid services are needed.

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
```

Windows: use `.venv\Scripts\python.exe` instead. Install Poppler and put
`pdftotext` on PATH (Ubuntu/Debian: `sudo apt-get install poppler-utils`;
Fedora: `sudo dnf install poppler-utils`; macOS: `brew install poppler`).
RapidOCR ships the local ONNX weights used by this build; the first installation
requires network access. Subsequent audited runs need no network access.

## Commands

Run from the repository root; paths are resolved relative to the source directory,
so another working directory also works:

```sh
.venv/bin/python code/main.py
.venv/bin/python code/evaluation/main.py
.venv/bin/python -m unittest discover -s code/tests -v
.venv/bin/python code/review.py
.venv/bin/python code/package.py
```

- `main.py` reads `dataset/`, audits all requests, validates every emitted step,
  and atomically writes root `output.csv` only when all cases resolve. Exit code
  2 means unresolved evidence/intent. Per-case diagnostics are written under
  `evaluation_runs/` before the failure is reported.
- `review.py` produces `evaluation_runs/review/partial_predictions.csv` plus
  `case_review.csv`, which lists every input case with explicit unresolved rows.
  **Neither is a valid 518-row submission.** Review mode cannot silently replace
  the root submission file.
- `evaluation/main.py` recomputes public sample predictions, counts unresolved
  cases as failures, and writes all metrics directly into its Markdown report.
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

## Architecture and tradeoffs

1. **Ingest** manifest-referenced evidence only. JSON structures, six operational
   log envelopes, SQL tables, text handovers and PDFs become typed observations.
   Local PP-OCRv6 detects/recognizes image text with bounding boxes and confidence.
2. **Link identities** using current and eligible historical emails, supplied
   hashes, stable user references and explicit catalog/trace links. SHA-256 is
   enabled only after checking every supplied current email/hash pair. No matching
   on names, phone numbers, numeric ID suffixes or evidence filenames.
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
adds measurable evidence extraction without API spend. Intent is a deliberately
bounded multilingual rule baseline; unfamiliar or unresolved conditional requests
fail for review. It is not a general multilingual language model.

## Evidence and evaluation limits

The report distinguishes parser defects that were fixed from unresolved evidence
associations and conflicting public expectations. Some absent/anonymized resources
have no supplied identity link, and some expected records occur only in later
captures. These are not filled using sample answers. Partial output may still
miss anonymous resources or phone-only links; 414 emitted decisions do not mean
414 independently verified correct answers.

Twenty-two isolated regression checks cover historical identity, decoys, multilingual
intent, prerequisites, cutoff leakage, replica drift, recreation, retention,
tombstones, backups, hostile SQL, path traversal and input metamorphisms. Public
sample evaluation is development evaluation: 22/32 status matches and 8/32 exact
sequences at this build, with unresolved cases included in the denominator.

## Artifacts and interview

- `code.zip`: source archive; currently a development deliverable.
- `code/evaluation/evaluation_report.md`: measured metrics and custom scenarios.
- `code/evaluation/usage_report.md`: actual local OCR calls, zero API tokens/cost.
- `log.txt`: authentic append-only coding-session summary; submit separately.
- `docs/trace_collection.md`: collect `agent-trace.zip` after closing active sessions.
- `docs/interview.md`: architecture, failures, costs and discussion questions.

The archive includes reports at both `code/evaluation/` and `evaluation/` to
satisfy the two documented layouts. The dataset remains external.
