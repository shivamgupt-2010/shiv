# Development & Deployment Guide

## 1. Local Development

### Virtual Environment Setup
```powershell
# In F:\cccccccccc\shivai
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
```

### Running Tests
```powershell
pytest -v
```

### Running Local Development Server
```powershell
uvicorn apps.api.main:app --host 0.0.0.0 --port 8000 --reload
```

---

## 2. Docker Deployment

### Build Image
```bash
docker build -t shivai-backend:v1 .
```

### Run with Docker Compose
```bash
docker compose up -d
```
