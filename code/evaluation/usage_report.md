# Usage report — current full-dataset run and historical API responses

## Current full-dataset run (no hosted calls)

The current code was run over all 518 evaluation requests:

```sh
.venv/bin/python code/main.py --allow-degraded --dataset dataset \
  --output output.csv --diagnostics evaluation_runs/final_run.json
```

The run produced 518 unique, lexically sorted rows: 153 `COMPLETE`, 355
`INCOMPLETE` and 10 `NOT_APPLICABLE`, with **1 unresolved `INCOMPLETE,[]`
fallback** (`case_63`). Output SHA-256:
`3c563f871040b1d9c225e7ed1693c420835195a2793bd1b549dc2c181772c844`.
The run reports `submission_ready: false`; it is a best-effort answer, not a
strict submission.

| Provider/model | Calls | Input tokens | Output tokens | Total tokens | Estimated cost |
|---|---:|---:|---:|---:|---:|
| Hosted overall (none) | 0 | 0 | 0 | 0 | $0 |

Hosted averages across the 518 requests: 0 tokens and $0 per request.
No provider usage is inferred from local prompt lengths or code execution.
No historical Groq proposal was replayed into this run.

Local RapidOCR models: `PP-OCRv6_det_small.onnx`, `PP-OCRv6_rec_small.onnx`,
`ch_ppocr_mobile_v2.0_cls_mobile.onnx`. The full run used 0 fresh OCR
invocations and 11 cache hits, producing 3030 observations from 94 evidence files
in 2.209 seconds. The public-sample run used 0 fresh OCR invocations and 11 cache
hits. Local inference has no provider token bill; electricity/hardware and
coding-agent usage are not measured.

The previous root artifact (SHA-256
`b2971b3c022f9bbda1b284d03b2320eff2d7df76deb7a713137ee067adc7f710`, 104 fallbacks)
is preserved at
`evaluation_runs/repair_session_20261025T1100Z/output_before_allow_degraded.csv`.
It was superseded by the current `--allow-degraded` run, which still cannot pass
the strict gate while `case_63` is unresolved.

## Historical Groq experiment (separate from this repair session)

Recomputed directly from 104 original `*_response.json` files in
`evaluation_runs/groq_refinement/`. These are historical measurements, not new
calls, cache hits, or accepted replacements in the current run. The journal
records 207 attempts; 103 attempts have no response usage and their tokens/billing
remain unknown.

| Provider/model | Responses with usage | Input (includes cached) | Cached input | Output | Total | Known estimated cost |
|---|---:|---:|---:|---:|---:|---:|
| Groq / `openai/gpt-oss-20b` | 104 | 154561 | 21504 | 37548 | 192109 | $0.022039323 |
| Historical overall | 104 | 154561 | 21504 | 37548 | 192109 | $0.022039323 |

Historical reported averages per 104 targeted requests: 1847.202 total tokens and
$0.000211917. Across the 518-request dataset: 370.867 tokens and $0.000042547.
Earlier OpenAI/Gemini credential or failed-generation experiments are not part of
this run; absent usage responses are not assigned invented token counts.

In this repair session the refiner was made target-count agnostic (it previously
hardcoded exactly 104 fallbacks) and now rejects a diagnostics/error-list
disagreement. It still requires an explicit `--max-cost-usd` budget and makes no
call without `GROQ_API_KEY`. No new paid calls were made.

Pricing: $0.075 per million uncached input tokens, $0.037 cached input, $0.30 output.
Source: [Groq GPT OSS 20B documentation](https://console.groq.com/docs/model/openai/gpt-oss-20b),
verified 2026-10-25. Cost = ((input-cached)*0.075 + cached*0.037 + output*0.30)/1,000,000.
These are list-price estimates, not a bill; free-tier treatment and unmetered
failures are excluded. Raw responses, request caches and credentials are excluded
from `code.zip`. No key is included in this report.
