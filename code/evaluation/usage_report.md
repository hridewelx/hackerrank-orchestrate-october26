# Usage report — final output and OpenAI refinement

`output.csv` contains 518 rows; 0 fallback rows
were replaced by validated model proposals, and 104 empty
fallbacks remain. Output SHA-256: `b2971b3c022f9bbda1b284d03b2320eff2d7df76deb7a713137ee067adc7f710`.
Only the original 104 unresolved evaluation cases may be sent to the API.
The key is loaded locally with python-dotenv and is never stored in reports,
request caches, output, Git, or code.zip.

| Provider/model | API attempts | Responses with usage | Input tokens | Cached input | Output tokens | Total tokens | Estimated known cost |
|---|---:|---:|---:|---:|---:|---:|---:|
| OpenAI / gpt-4o-mini | 2 | 0 | 0 | 0 | 0 | 0 | $0.000000 |
| Overall hosted totals | 2 | 0 | 0 | 0 | 0 | 0 | $0.000000 |

Across all 518 output requests: 0.000 reported tokens
and $0.00000000 known estimated API cost per request.
Across the 104 targeted cases: 0.000 reported tokens and
$0.00000000 known estimated cost per targeted case.
Calls that fail or are interrupted without usage cannot be assigned invented
token counts or billed costs; 2 attempt(s) have no usage record.
Recorded totals above exclude unknown usage and are not a billing reconciliation.

Rates per million tokens: input $0.15, cached input $0.075, output $0.60.
Source: [official gpt-4o-mini model documentation](https://developers.openai.com/api/docs/models/gpt-4o-mini),
checked 2026-10-24. The runtime uses only the requested `gpt-4o-mini` alias;
returned model identifiers are recorded per response in the local ledger.
Run cap: $1.00; max response tokens: 4096.
No automatic provider retries. Completed responses are cached; pending or failed
calls are not silently retried, preventing duplicate untracked charges.

The preceding local full run used 11 RapidOCR image
invocations and 0 OCR cache hits, producing
3025 observations from 94 files.
The refinement's additional OCR invocations/cache hits are
0/22. Local OCR has no API
token billing; CPU/electricity costs are not estimated. Models remain
PP-OCRv6_det_small.onnx, PP-OCRv6_rec_small.onnx and
ch_ppocr_mobile_v2.0_cls_mobile.onnx. Coding-assistant usage is separate and unknown.

Baseline diagnostics, immutable target IDs, per-case prompt hashes, API response
metadata, usage and rejection reasons are in evaluation_runs/openai_refinement/.
These local caches are excluded from code.zip.
