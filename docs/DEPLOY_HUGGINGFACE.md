# Deploying ShivAI to Hugging Face Spaces (100% Free 24/7 Hosting)

Hugging Face Spaces provides a **free, dedicated 24/7 container** with:
* **16 GB of RAM**
* **2 vCPUs**
* **50 GB storage**
* **Never sleeps** (stays online permanently)
* **Zero credit card required**

---

## Method 1: 1-Click Automated Deployment (Fastest)

We built an automated deploy script in `scripts/deploy_to_huggingface.py`.

### Step 1: Get a Free Hugging Face Token
1. Go to [huggingface.co/settings/tokens](https://huggingface.co/settings/tokens) (create a free account if you haven't yet).
2. Click **Create new token** (or use an existing one).
3. Select Type: **Write** (allows creating the Space and uploading code).
4. Copy your token (starts with `hf_...`).

### Step 2: Run the Deploy Script
Run this single command from your project directory:

```powershell
& "F:\cccccccccc\shivai\.venv\Scripts\python.exe" scripts/deploy_to_huggingface.py --token hf_YOUR_TOKEN_HERE
```

The script will automatically:
1. Create a private Space called `shivai-backend` on your Hugging Face account.
2. Upload your ShivAI backend code (excluding virtualenvs and local secrets).
3. Trigger the 24/7 Docker build.

---

## Method 2: Manual Web UI Upload (If you prefer browser)

1. Go to [huggingface.co/new-space](https://huggingface.co/new-space).
2. Set Space Name: `shivai-backend`.
3. Set License: `MIT`.
4. Select Space SDK: **Docker** (Blank).
5. Choose Visibility: **Private** (or Public).
6. Click **Create Space**.
7. In the Space page, click **Files** → **Upload files**.
8. Upload the project files (`Dockerfile`, `requirements.txt`, `apps/`, `core/`, `config/`, `database/`, `providers/`, `security/`, `monitoring/`, `README.md`).

---

## Adding Your AI Keys in Hugging Face (Required)

Once your Space is created:
1. Go to your Space settings: `https://huggingface.co/spaces/YOUR_USERNAME/shivai-backend/settings`.
2. Scroll down to **Variables and secrets**.
3. Under **Secrets**, click **New secret** and add:
   * **`GEMINI_API_KEY`**: `your_gemini_api_key_here`
   * **`GROQ_API_KEY`**: `your_groq_api_key_here`
   * **`SHIVAI_API_KEY`**: `your_shivai_api_key_here`
4. Hugging Face will automatically restart your container with your keys loaded!

---

## Connecting Your Client or SDK to Hugging Face

Once your Space shows **"Running"**, its public URL is:
`https://YOUR_USERNAME-shivai-backend.hf.space/api/v1`

You can connect to it from any computer, phone, or tablet with your computer turned off:

```python
from shivai import ShivAI

client = ShivAI(
    api_key="shivai-secret-key-123",
    base_url="https://YOUR_USERNAME-shivai-backend.hf.space/api/v1"
)

response = client.chat.create("Hello ShivAI, are you online?")
print(response.content)
```
