"""
1-Click Automated Deployment Script for Hugging Face Spaces.
Creates a 24/7 Docker Space, uploads the ShivAI code, and sets up live hosting.
"""
import sys
import argparse
from pathlib import Path
from huggingface_hub import HfApi

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def deploy(repo_id: str, token: str, private: bool = True):
    print(f"Connecting to Hugging Face with provided token...")
    api = HfApi(token=token)

    try:
        user_info = api.whoami()
        username = user_info.get("name", "user")
        print(f"Authenticated as: {username}")
    except Exception as e:
        print(f"Authentication failed: {e}")
        print("Please check your Hugging Face Access Token.")
        sys.exit(1)

    if "/" not in repo_id:
        repo_id = f"{username}/{repo_id}"

    print(f"\n1. Checking Space: {repo_id} (type=gradio, zero-Docker)...")
    try:
        api.create_repo(
            repo_id=repo_id,
            repo_type="space",
            space_sdk="gradio",
            private=private,
            exist_ok=True,
        )
        print("Space verified/created on Hugging Face!")
    except Exception as e:
        print(f"Notice on Space creation: {e}")
        print("If the Space was not created via API, you can create it in 10 seconds at: https://huggingface.co/new-space")

    print("\n2. Uploading ShivAI codebase to Hugging Face Space...")
    # Ignore virtualenvs, secrets, databases, and heavy local model weights
    ignore_patterns = [
        ".venv/**",
        ".git/**",
        ".env*",
        "*.db",
        "*.sqlite",
        "*.sqlite3",
        "models/*.gguf",
        "__pycache__/**",
        ".pytest_cache/**",
    ]

    try:
        commit_info = api.upload_folder(
            folder_path=str(PROJECT_ROOT),
            repo_id=repo_id,
            repo_type="space",
            ignore_patterns=ignore_patterns,
            commit_message="Deploy ShivAI AI Backend to Hugging Face Spaces",
        )
        print(f"Code successfully uploaded! Commit: {commit_info}")
    except Exception as e:
        print(f"Upload failed: {e}")
        sys.exit(1)

    space_name = repo_id.split("/")[-1]
    host_slug = f"{username.lower()}-{space_name.lower().replace('_', '-')}.hf.space"

    print("\n=================================================================")
    print("SUCCESS: ShivAI is deploying to Hugging Face Spaces!")
    print(f"Space Dashboard: https://huggingface.co/spaces/{repo_id}")
    print(f"Live App Endpoint: https://{host_slug}")
    print("=================================================================")
    print("\nNEXT STEPS:")
    print(f"1. Open https://huggingface.co/spaces/{repo_id}/settings")
    print("2. Scroll down to 'Variables and secrets' -> click 'New secret':")
    print("   - Name: GEMINI_API_KEY")
    print("   - Name: GROQ_API_KEY")
    print("3. Your Space will build the Docker container and stay online 24/7 with 16 GB of RAM!")


def main():
    parser = argparse.ArgumentParser(description="Deploy ShivAI to Hugging Face Spaces")
    parser.add_argument("--repo", type=str, default="shivai-backend", help="Space name (e.g. your-username/shivai-backend)")
    parser.add_argument("--token", type=str, required=True, help="Hugging Face Access Token (from https://huggingface.co/settings/tokens)")
    parser.add_argument("--public", action="store_true", help="Make Space public (default is private)")

    args = parser.parse_args()
    deploy(repo_id=args.repo, token=args.token, private=not args.public)


if __name__ == "__main__":
    main()
