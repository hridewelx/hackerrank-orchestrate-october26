# Usage report — final full-dataset run

The final full-dataset run produced root `output.csv`: 518 of
518 rows, including 104 conservative fallback rows
(INCOMPLETE with empty steps). These fallback rows remain unproven. All cases
were attempted. python-dotenv loaded local configuration; no credentials were
printed, transmitted, or included in artifacts. No hosted API calls were made.

| Provider / model | Calls | Input tokens | Output tokens | Total tokens | Estimated API cost |
|---|---:|---:|---:|---:|---:|
| Local RapidOCR 3.10.0 pipeline | 11 image invocations | N/A (images) | N/A (OCR characters) | N/A | $0 |
| Hosted language models | 0 | 0 | 0 | 0 | $0 |
| Overall hosted/API totals | 0 | 0 | 0 | 0 | $0 |

Per evaluation request: 0 language-model input/output tokens, 0 average tokens,
and $0 estimated API spend. Local CPU/hardware/electricity cost is not estimated.
OCR text must not be mislabeled as LLM output tokens. Calls count outer image
pipeline invocations; internal crop recognition executions are not individually
metered. The pipeline's components are:

- `PP-OCRv6_det_small.onnx`; SHA-256 `090f04abcd9d9a7498bc4ebf677e4cb9bdce1fe4197ddb7e529f1ef44e1ff94f`.
- `PP-OCRv6_rec_small.onnx`; SHA-256 `6f327246b50388f3c176ae304bd95767ea6dc0c9ae92153ef8cbe210b3c14884`.
- `ch_ppocr_mobile_v2.0_cls_mobile.onnx`; SHA-256 `e47acedf663230f8863ff1ab0e64dd2d82b838fceb5957146dab185a89d6215c`.

Final cold run: OCR cache bypassed; 11 image invocations,
0 cache hits, 44.208 seconds. Read 94
evidence files and produced 3025 typed observations.
Output SHA-256: `b2971b3c022f9bbda1b284d03b2320eff2d7df76deb7a713137ee067adc7f710`.
The preceding strict/review build also demonstrated deterministic warm-cache replay.

This demonstrates cached replay and deterministic planning/serialization. It is
not a claim about independent generative-model determinism. There is no paid model
ablation, provider token estimate or pricing-rate assumption because no paid API
was called. Exact OCR/runtime versions are pinned in requirements.txt; model weight
hashes above identify the observed installed weights.

Coding-assistant development usage (Codex Desktop / gpt-6-astra) is separate from
the submitted runtime. Per-call development costs are not available to the solution
and are not invented or counted as zero. The authentic rollout can supply whatever
usage metadata the harness recorded after the active session is closed.
