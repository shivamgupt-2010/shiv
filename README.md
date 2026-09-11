---
title: ShivAI
emoji: ⚡
colorFrom: indigo
colorTo: purple
sdk: gradio
sdk_version: 6.26.0
app_file: app.py
pinned: false
---

# ShivAI AI Backend V1

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.111+-009688.svg)](https://fastapi.tiangolo.com)
[![SQLAlchemy 2.0](https://img.shields.io/badge/SQLAlchemy-2.0+-red.svg)](https://www.sqlalchemy.org/)
[![Pydantic v2](https://img.shields.io/badge/Pydantic-v2+-e92063.svg)](https://docs.pydantic.dev/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

**ShivAI** is an independent, production-grade AI backend designed so that the underlying external AI models can rotate, change, and automatically fail-over without ever altering ShivAI's identity, personality, context, persistent memory, or conversation continuity.

The user experiences **one unified AI companion named ShivAI**, regardless of whether OpenAI, Anthropic, Google Gemini, Groq, DeepSeek, or Mistral fulfills an individual message turn.

---

## Table of Contents

- [Architecture Overview](#architecture-overview)
- [Key Features](#key-features)
- [Provider Support](#provider-support)
- [Quick Start](#quick-start)
- [Environment Variables](#environment-variables)
- [API Endpoints](#api-endpoints)
- [Model Routing & Fallback Logic](#model-routing--fallback-logic)
- [Persistent Memory Subsystem](#persistent-memory-subsystem)
- [Testing & Verification](#testing--verification)
- [Adding a New Provider](#adding-a-new-provider)
- [Security & Redaction](#security--redaction)
- [Documentation Index](#documentation-index)

---

## Architecture Overview

```
                         CLIENT INTERFACE
        (REST API / SSE Streaming / Android / Web / Desktop)
                               │
                               ▼
                      SHIVAI API GATEWAY
         (Auth, Rate Limiting, RequestID, Security Headers)
                               │
                               ▼
                          SHIVAI CORE
  ┌────────────────────────────┼────────────────────────────┐
  │                            │                            │
  ▼                            ▼                            ▼
IDENTITY MANAGER        CONTEXT ENGINE                MEMORY SUBSYSTEM
(Immutable Persona      (Token Budget Aware,         (Short-term History,
 & System Directives)    Dynamic Pruning)             Long-term User Facts)
  │                            │                            │
  └────────────────────────────┼────────────────────────────┘
                               │
                               ▼
                        AI ORCHESTRATOR
                (Intent, Capabilities, Agents, Tools)
                               │
                               ▼
                         MODEL ROUTER
        (Dynamic Scoring, Capability Matching, Cooldown Filter)
                               │
                               ▼
                       FALLBACK HANDLER
         (Failover Loop, Cooldowns, Error Classification)
                               │
       ┌───────────┬───────────┼───────────┬───────────┐
       ▼           ▼           ▼           ▼           ▼
    OpenAI     Anthropic     Gemini      Groq      DeepSeek / Mistral
```

---

## Key Features

1. **Immutable ShivAI Identity**: Core persona, communication style, and ethical guardrails are injected uniformly into every model via `core/identity/identity_manager.py`. Models are intelligence engines, not personas.
2. **Dynamic Multi-Model Router**: Models are filtered by required capabilities (reasoning, vision, tools, coding, streaming) and ranked by priority, latency, and real-time health.
3. **Zero-Disruption Automatic Fallback**: If a provider experiences quota exhaustion (`429`), rate limits, timeouts, or auth failures, ShivAI automatically fails over to the next best provider without dropping the conversation.
4. **Adaptive Cooldown Management**: Quota-exhausted providers are given a cooldown to prevent repetitive requests, while rate-limited providers are throttled according to `Retry-After` headers.
5. **Two-Tier Persistent Memory**:
   - Short-term session memory: Multi-turn message history per conversation thread.
   - Long-term semantic memory: User facts, coding preferences, and persistent profiles.
6. **Server-Sent Events (SSE) Streaming**: Progressive token streaming with unified chunk schemas (`/api/v1/chat/stream`).
7. **Production Security**:
   - API key validation (`X-API-Key` or Bearer token).
   - In-memory sliding-window rate limiting.
   - Zero key leakage: Automated secret redaction across all logs, error messages, and API traces.
8. **Asynchronous Architecture**: Built on FastAPI, HTTPX, and SQLAlchemy 2.0 Async Engine with SQLite or PostgreSQL.

---

## Provider Support

Out-of-the-box support for 6 premier providers plus generic OpenAI-compatible APIs:

| Provider | Supported Models | Adapter Implementation |
| :--- | :--- | :--- |
| **OpenAI** | GPT-4o, GPT-4o-mini | `providers/openai/` |
| **Anthropic** | Claude 3.5 Sonnet, Claude 3.5 Haiku | `providers/anthropic/` |
| **Google Gemini** | Gemini 1.5 Pro, Gemini 2.0 Flash | `providers/gemini/` |
| **Groq** | Llama 3.3 70B Versatile, Mixtral | `providers/groq/` |
| **DeepSeek** | DeepSeek-Chat (V3), DeepSeek-Reasoner (R1) | `providers/deepseek/` |
| **Mistral AI** | Mistral Large, Codestral | `providers/mistral/` |
| **Generic OpenAI** | OpenRouter, Perplexity, Together, Ollama, vLLM | `providers/generic_openai/` |

---

## Quick Start

### 1. Prerequisites
- Python 3.11+
- Git

### 2. Setup Virtual Environment & Dependencies
```bash
# Clone or navigate to the repository
cd shivai

# Create virtual environment
python -m venv .venv

# Activate virtual environment
# Windows:
.venv\Scripts\activate
# Linux/macOS:
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### 3. Configure Environment Variables
```bash
cp .env.example .env
```
Edit `.env` and configure your API keys. You do **not** need all 6 keys; ShivAI operates with any available keys and routes accordingly.

### 4. Run Database Migrations
```bash
alembic upgrade head
```

### 5. Launch Server
```bash
uvicorn apps.api.main:app --host 0.0.0.0 --port 8000 --reload
```

Interactive API documentation will be live at:
- **Swagger UI**: [http://localhost:8000/docs](http://localhost:8000/docs)
- **ReDoc**: [http://localhost:8000/redoc](http://localhost:8000/redoc)

---

## API Endpoints

### Chat & Streaming
- `POST /api/v1/chat` — Synchronous chat turn with automatic model routing and failover.
- `POST /api/v1/chat/stream` — Real-time SSE token streaming.

### Memory & Conversations
- `GET /api/v1/conversations` — List conversation threads for caller.
- `GET /api/v1/conversations/{id}` — Fetch conversation turns and metadata.
- `POST /api/v1/conversations` — Create a new conversation thread.
- `GET /api/v1/memory` — Search or list active long-term memories.
- `POST /api/v1/memory` — Store a new persistent user fact or preference.
- `DELETE /api/v1/memory/{id}` — Remove an active memory item.

### Observability & Models
- `GET /api/v1/models` — List model catalog, capabilities, and provider status.
- `GET /api/v1/health` — Basic service health check.
- `GET /api/v1/health/providers` — Real-time provider health, status, and error metrics.
- `GET /api/v1/metrics` — Aggregate token counts, latencies, and request performance.

---

## Model Routing & Fallback Logic

```
Incoming Request
       │
       ▼
Task Classification (coding, math, research, general)
       │
       ▼
Capability Filtering (requires: vision? reasoning? tools? coding?)
       │
       ▼
Health Filtering (excludes: AUTH_FAILED, active QUOTA_EXHAUSTED cooldown)
       │
       ▼
Priority Scoring (score = priority + affinity_bonus + capability_bonus)
       │
       ▼
Sorted Candidate Pool: [Candidate 1, Candidate 2, Candidate 3, ...]
       │
       ├─► Attempt Candidate 1 ──► [SUCCESS] ──► Record metrics & return as ShivAI
       │
       └─► [FAILURE] (e.g. 429 Quota Exceeded)
                 │
                 ▼
           Classify Error -> QUOTA_EXCEEDED
           Set Provider Cooldown in DB (900s)
                 │
                 ▼
           Attempt Candidate 2 ──► [SUCCESS] ──► Return as ShivAI
```

---

## Testing & Verification

Run the full automated test suite (unit tests, provider failure simulations, SSE streaming, and integration tests):

```bash
pytest -v
```

All 31 automated tests verify:
- Complete end-to-end chat turn and conversation history.
- Real-time SSE streaming.
- Immediate failover when primary provider quota is exhausted.
- Respect of rate-limit cooldowns and retry-after headers.
- Graceful recovery when network timeout or server errors occur.
- Total identity continuity across multi-turn provider switches.
- Zero secret leakage in logs, traces, or responses.

---

## Security & Redaction

- **Zero Plaintext Credentials**: API keys are loaded strictly from environment variables at runtime.
- **Automated Redactor**: Regex and exact-match patterns scrub all known vendor keys (`sk-...`, `AIza...`, `gsk_...`, Bearer tokens) from application logs and error messages before output.
- **Tool Sandbox**: Built-in tools like the AST Calculator parse abstract syntax trees to prevent arbitrary code execution (`eval()` is strictly prohibited).
