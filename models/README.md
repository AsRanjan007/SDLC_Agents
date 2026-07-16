# Local models

Place your local **GGUF** model file(s) here (or anywhere on the device) and set
the path in the app under **Settings → Agent LLM connection → Local GGUF model**.

Models are intentionally **git-ignored** (`*.gguf`, `*.bin`, `*.safetensors`) so
confidential/large files never leave the device.

## Recommended small, edge-friendly models

Download **once** on a connected machine, then copy to the air-gapped/edge
device (no download happens inside the app):

| Model | Approx size (Q4) | Notes |
|-------|------------------|-------|
| Qwen2.5-0.5B-Instruct | ~0.4 GB | Smallest; fast on CPU |
| Qwen2.5-1.5B-Instruct | ~1.0 GB | Good quality/size balance |
| Llama-3.2-1B-Instruct | ~0.8 GB | Solid instruction following |
| Phi-3-mini-4k-Instruct | ~2.3 GB | Higher quality, larger |

Any GGUF chat model compatible with `llama-cpp-python` works.

## No model? No problem.

If no model is configured, the app uses its built-in **deterministic offline
engine** — the full flow (architecture, code, tests, validation report,
narration) still runs with zero model and zero network.
