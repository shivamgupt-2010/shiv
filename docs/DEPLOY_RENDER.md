# Deploying ShivAI to Render (Free 24/7 Hosting)

This guide shows how to deploy ShivAI to [Render.com](https://render.com) for **100% free** and configure it to **stay awake 24/7 without sleeping**.

---

## 1. What We Already Configured for You

We have already configured:
1. `Dockerfile`: Optimized multi-stage container that auto-binds to Render's dynamic `$PORT`.
2. `render.yaml`: Official Render Blueprint that automatically configures health checks (`/api/v1/health`), environment variables, and Docker build.
3. `.gitignore`: Protects your local `.env` and SQLite files from ever being leaked.

---

## 2. Step-by-Step Deployment (Takes ~3 Minutes)

### Step 1: Upload Your Code to GitHub
1. Create a new repository on [GitHub](https://github.com/new) named `shivai-backend` (make it **Private** for your security).
2. Upload the project folder `F:\cccccccccc\shivai` to your GitHub repo.
   *(Make sure your `.env` is NOT uploaded; your secrets stay safe on your computer!)*

### Step 2: Connect to Render
1. Go to [dashboard.render.com](https://dashboard.render.com/) and sign in (or create a free account).
2. Click the **New +** button in the top bar and select **Blueprint** (or **Web Service**).
3. Connect your GitHub repository `shivai-backend`.
4. Render will detect `render.yaml` automatically:
   - Name: `shivai-backend`
   - Runtime: `Docker`
   - Plan: `Free`
5. Click **Apply** (or **Create Web Service**).

### Step 3: Add Your Gemini API Key
In your Render Service dashboard:
1. Click **Environment**.
2. Find `GEMINI_API_KEY` and paste your key: `your_gemini_api_key_here`
3. Add `GROQ_API_KEY`: `your_groq_api_key_here`
4. Click **Save Changes**.

Render will now build your Docker container. In ~2 minutes, your service will show **"Live"** and give you a public URL like:
`https://shivai-backend-xxxx.onrender.com`

---

## 3. How to Prevent Render From Sleeping (Keep It Awake 24/7)

By default, Render's free tier spins down after 15 minutes of inactivity. To keep ShivAI running 24/7 with **zero cold starts**, use free uptime monitoring:

1. Create a free account at [UptimeRobot.com](https://uptimerobot.com/) (100% free).
2. Click **Add New Monitor**:
   - **Monitor Type**: `HTTP(s)`
   - **Friendly Name**: `ShivAI Keep-Alive`
   - **URL**: `https://your-app-name.onrender.com/api/v1/health`
   - **Monitoring Interval**: `Every 10 minutes`
3. Click **Create Monitor**.

### How this works:
UptimeRobot will send a lightweight ping (`GET /api/v1/health`) to your server every 10 minutes. Because Render receives an incoming request every 10 minutes, **Render never sleeps and stays awake 24/7/365**!

---

## 4. Connecting Your Clients & SDK to Render

Once live, update your SDK or frontend:

```python
from shivai import ShivAI

# Point to your 24/7 cloud URL!
client = ShivAI(
    api_key="your-key-from-render",
    base_url="https://your-app-name.onrender.com/api/v1"
)

response = client.chat.create("Hello ShivAI!")
print(response.content)
```

You can now turn off your computer completely—ShivAI is running 24/7 in the cloud!
