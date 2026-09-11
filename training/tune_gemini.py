"""
Google Gemini Fine-Tuning CLI & Cloud Orchestrator.
Communicates directly with Google AI Studio's tunedModels API to submit,
monitor, and deploy fine-tuned ShivAI intelligence models.
"""
import sys
import json
import time
import argparse
import httpx
from pathlib import Path

# Ensure project root is on sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from config.settings import settings


class GeminiTuningOrchestrator:
    def __init__(self, api_key: str = None):
        self.api_key = api_key or settings.GEMINI_API_KEY
        if not self.api_key:
            raise ValueError("GEMINI_API_KEY is required to launch or query tuning jobs.")
        self.base_url = "https://generativelanguage.googleapis.com/v1beta"

    def _headers(self):
        return {
            "Content-Type": "application/json",
            "x-goog-api-key": self.api_key,
        }

    async def list_tuned_models(self):
        """Lists all existing fine-tuned models created under this API key."""
        url = f"{self.base_url}/tunedModels"
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.get(url, headers=self._headers())
            resp.raise_for_status()
            data = resp.json()
            return data.get("tunedModels", [])

    async def get_tuned_model(self, model_id: str):
        """Fetches status and metadata of a specific fine-tuned model."""
        clean_id = model_id.removeprefix("tunedModels/")
        url = f"{self.base_url}/tunedModels/{clean_id}"
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.get(url, headers=self._headers())
            resp.raise_for_status()
            return resp.json()

    async def create_tuned_model(
        self,
        dataset_path: Path,
        display_name: str = "ShivAI-v1",
        base_model: str = "models/gemini-1.5-flash-001",
        epochs: int = 5,
        batch_size: int = 4,
        learning_rate: float = 0.001,
    ):
        """Submits a supervised fine-tuning job with training dataset."""
        if not dataset_path.exists():
            raise FileNotFoundError(f"Dataset file not found: {dataset_path}")

        # Read JSONL dataset
        examples = []
        with open(dataset_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    examples.append(json.loads(line))

        # Format examples for tunedModels API
        formatted_examples = []
        for item in examples:
            if "messages" in item:
                # Multi-turn messages format
                formatted_examples.append(item)
            elif "text_input" in item and "output" in item:
                formatted_examples.append({
                    "text_input": item["text_input"],
                    "output": item["output"],
                })

        payload = {
            "display_name": display_name,
            "base_model": base_model,
            "tuning_task": {
                "hyperparameters": {
                    "epoch_count": epochs,
                    "batch_size": batch_size,
                    "learning_rate": learning_rate,
                },
                "training_data": {
                    "examples": {
                        "examples": formatted_examples
                    }
                }
            }
        }

        url = f"{self.base_url}/tunedModels"
        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(url, headers=self._headers(), json=payload)
            resp.raise_for_status()
            return resp.json()


async def main():
    parser = argparse.ArgumentParser(description="ShivAI Gemini Fine-Tuning CLI")
    parser.add_argument("--list", action="store_true", help="List all fine-tuned models")
    parser.add_argument("--status", type=str, help="Check status of a specific tuned model ID")
    parser.add_argument("--create", action="store_true", help="Submit a new fine-tuning job")
    parser.add_argument("--name", type=str, default="ShivAI-v1", help="Display name for the model")
    parser.add_argument("--epochs", type=int, default=5, help="Number of training epochs")
    parser.add_argument("--dataset", type=str, default="training/gemini_tuning_dataset.jsonl")
    args = parser.parse_args()

    orchestrator = GeminiTuningOrchestrator()

    if args.list:
        print("Fetching fine-tuned models from Google AI...")
        models = await orchestrator.list_tuned_models()
        if not models:
            print("No fine-tuned models found currently under this API key.")
        else:
            print(f"Found {len(models)} fine-tuned models:")
            for m in models:
                print(f" - Name: {m.get('name')}")
                print(f"   State: {m.get('state')}")
                print(f"   Base:  {m.get('baseModel')}")
        return

    if args.status:
        print(f"Fetching status for {args.status}...")
        meta = await orchestrator.get_tuned_model(args.status)
        print(json.dumps(meta, indent=2))
        return

    if args.create:
        dataset_file = Path(args.dataset)
        if not dataset_file.is_absolute():
            dataset_file = PROJECT_ROOT / dataset_file

        print(f"Submitting fine-tuning job '{args.name}' using {dataset_file}...")
        try:
            result = await orchestrator.create_tuned_model(
                dataset_path=dataset_file,
                display_name=args.name,
                epochs=args.epochs,
            )
            print("Job created successfully!")
            print(json.dumps(result, indent=2))
        except httpx.HTTPStatusError as e:
            print(f"API Error ({e.response.status_code}): {e.response.text}")


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
