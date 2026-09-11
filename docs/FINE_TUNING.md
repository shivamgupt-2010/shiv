# ShivAI Model Fine-Tuning & Hosting Guide

This guide explains how to fine-tune an open-source or commercial base AI model to permanently encode the **ShivAI identity**, behavioral rules, and technical persona into model weights, host it, and bind it to the ShivAI backend.

---

## 1. Dataset Generation

The dataset generator creates specialized training data in multiple standard formats:

```powershell
# Run the dataset generator
python training/dataset_generator.py
```

Generated outputs in `training/`:
- `training/gemini_tuning_dataset.jsonl` — Multi-turn chat format for Google AI Studio / Gemini API.
- `training/alpaca_tuning_dataset.json` — Instruction/Response format for Unsloth / Hugging Face / Llama / Qwen.
- `training/openai_tuning_dataset.jsonl` — Format for OpenAI fine-tuning.

---

## 2. Fine-Tuning Pathways

### Path A: Google AI Studio 1-Click Cloud Fine-Tuning (Zero Local GPU Needed)

Google AI Studio provides free/included compute on Google TPUs/GPUs and **permanently hosts** the fine-tuned model with high-availability REST endpoints.

1. Navigate to [Google AI Studio](https://aistudio.google.com/).
2. In the left navigation, click **Tune Model** (or **Create Tuned Model**).
3. Select Base Model: `Gemini 1.5 Flash` (or `Gemini 2.5 Flash`).
4. Upload your training dataset: `F:\cccccccccc\shivai\training\gemini_tuning_dataset.jsonl`.
5. Name the model: `shivai-v1`.
6. Click **Tune**.
7. Once training finishes, copy the model identifier (e.g. `tunedModels/shivai-v1`).
8. Add it to `config/models_config.yaml` as the `#1` priority model (see Section 3).

---

### Path B: Free Google Colab 1-Click Fine-Tuning (Llama 3.2 / Qwen 2.5)

To fine-tune an open-weights model on a free cloud GPU:

1. Open [Google Colab](https://colab.research.google.com/).
2. Open `training/colab_unsloth_finetune.ipynb`.
3. Upload `training/alpaca_tuning_dataset.json` to the Colab files pane.
4. Set Runtime to **T4 GPU** (free tier).
5. Run all cells:
   - Installs Unsloth and loads `unsloth/Llama-3.2-3B-Instruct` in 4-bit.
   - Fine-tunes with LoRA in ~10 minutes.
   - Exports a `.gguf` file or uploads to your Hugging Face account.
6. Host locally with Ollama:
   ```bash
   ollama create shivai -f Modelfile
   ollama run shivai
   ```
   Or connect your Ollama endpoint to ShivAI via `GENERIC_OPENAI_BASE_URL=http://localhost:11434/v1`.

---

### Path C: OpenAI Supervised Fine-Tuning (GPT-4o-mini)

```powershell
python training/tune_openai.py
```
This automatically converts the dataset, uploads it to OpenAI's Files API, and triggers an automated fine-tuning job on `gpt-4o-mini-2024-07-18`.

---

## 3. Registering the Fine-Tuned Model in ShivAI

Once your fine-tuned model is created and hosted, add it to `config/models_config.yaml`:

```yaml
models:
  - id: shivai_custom_tuned
    provider: gemini # or openai / generic_openai
    model: tunedModels/shivai-v1 # your tuned model ID
    priority: 100 # Highest priority
    capabilities:
      reasoning: true
      vision: true
      tools: true
      streaming: true
      coding: true
    context_limit: 1000000
    max_output_tokens: 8192
    cost_tier: low
    status: active
```

The ShivAI Model Router will immediately identify `priority: 100` and route all primary queries to your fine-tuned model, while gracefully falling back to other providers if any error occurs!
