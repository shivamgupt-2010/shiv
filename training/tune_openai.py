"""
OpenAI Fine-Tuning CLI & Automation.
Uploads ShivAI training dataset and submits an automated fine-tuning job on OpenAI (e.g. gpt-4o-mini).
"""
import sys
import json
import httpx
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from config.settings import settings


def prepare_openai_dataset(input_jsonl: Path, output_jsonl: Path) -> int:
    """Converts dataset into OpenAI Chat Completion fine-tuning format."""
    count = 0
    with open(input_jsonl, "r", encoding="utf-8") as fin, open(output_jsonl, "w", encoding="utf-8") as fout:
        for line in fin:
            if not line.strip():
                continue
            item = json.loads(line)
            # Ensure roles match: system, user, assistant
            messages = []
            for m in item.get("messages", []):
                role = m["role"]
                if role == "model":
                    role = "assistant"
                messages.append({"role": role, "content": m["content"]})
            fout.write(json.dumps({"messages": messages}, ensure_ascii=False) + "\n")
            count += 1
    return count


async def submit_openai_tuning(api_key: str, dataset_file: Path, model: str = "gpt-4o-mini-2024-07-18"):
    headers = {"Authorization": f"Bearer {api_key}"}
    async with httpx.AsyncClient(timeout=60.0) as client:
        # 1. Upload file
        print(f"Uploading {dataset_file.name} to OpenAI Files API...")
        with open(dataset_file, "rb") as f:
            files = {"file": (dataset_file.name, f, "application/jsonl")}
            data = {"purpose": "fine-tune"}
            resp = await client.post("https://api.openai.com/v1/files", headers=headers, data=data, files=files)
            resp.raise_for_status()
            file_id = resp.json()["id"]
            print(f"File uploaded. File ID: {file_id}")

        # 2. Submit job
        print(f"Submitting fine-tuning job for base model {model}...")
        job_payload = {
            "training_file": file_id,
            "model": model,
            "suffix": "shivai-v1",
        }
        job_resp = await client.post("https://api.openai.com/v1/fine_tuning/jobs", headers=headers, json=job_payload)
        job_resp.raise_for_status()
        job_data = job_resp.json()
        print(f"Job submitted successfully! Job ID: {job_data['id']}")
        return job_data


if __name__ == "__main__":
    import asyncio
    in_path = PROJECT_ROOT / "training" / "gemini_tuning_dataset.jsonl"
    out_path = PROJECT_ROOT / "training" / "openai_tuning_dataset.jsonl"
    c = prepare_openai_dataset(in_path, out_path)
    print(f"Prepared OpenAI dataset with {c} examples at {out_path}")
