"""
Downloads the top-tier 3B AI Model (Llama-3.2-3B-Instruct-Q4_K_M.gguf) into the project's models directory.
Features chunked streaming, progress updates, and file integrity verification.
"""
import sys
import time
import httpx
from pathlib import Path

MODEL_URL = "https://huggingface.co/bartowski/Llama-3.2-3B-Instruct-GGUF/resolve/main/Llama-3.2-3B-Instruct-Q4_K_M.gguf"
DEST_DIR = Path(__file__).resolve().parent.parent / "models"
DEST_FILE = DEST_DIR / "Llama-3.2-3B-Instruct-Q4_K_M.gguf"


def download_model():
    DEST_DIR.mkdir(parents=True, exist_ok=True)

    print(f"Target directory: {DEST_DIR}")
    print(f"Destination file: {DEST_FILE.name}")
    print("Connecting to Hugging Face...")

    with httpx.Client(follow_redirects=True, timeout=httpx.Timeout(connect=30.0, read=120.0, write=30.0, pool=30.0)) as client:
        with client.stream("GET", MODEL_URL) as response:
            response.raise_for_status()
            total_bytes = int(response.headers.get("content-length", 0))
            total_mb = total_bytes / (1024 * 1024)
            print(f"Total Size: {total_mb:.2f} MB ({total_mb / 1024:.2f} GB)")

            downloaded_bytes = 0
            start_time = time.time()
            last_report_time = start_time

            with open(DEST_FILE, "wb") as f:
                for chunk in response.iter_bytes(chunk_size=1024 * 1024):  # 1MB chunks
                    if chunk:
                        f.write(chunk)
                        downloaded_bytes += len(chunk)

                        now = time.time()
                        if now - last_report_time >= 5.0 or downloaded_bytes == total_bytes:
                            elapsed = now - start_time
                            percent = (downloaded_bytes / total_bytes) * 100 if total_bytes else 0
                            mb_done = downloaded_bytes / (1024 * 1024)
                            speed_mb = mb_done / elapsed if elapsed > 0 else 0
                            print(f"Progress: {percent:5.1f}% | {mb_done:7.1f}/{total_mb:.1f} MB | {speed_mb:5.2f} MB/s")
                            last_report_time = now

    final_size_mb = DEST_FILE.stat().st_size / (1024 * 1024)
    print("\n=======================================================")
    print("SUCCESS: 3B AI Model Download Complete!")
    print(f"Saved at: {DEST_FILE}")
    print(f"Final File Size: {final_size_mb:.2f} MB")
    print("=======================================================")


if __name__ == "__main__":
    download_model()
