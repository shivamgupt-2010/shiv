# ShivAI Architecture Specification

## 1. Architectural Philosophy

ShivAI separates **identity, state, and decision-making** from the **intelligence engines** (underlying LLMs).

External AI models are non-permanent cognitive processors. ShivAI is the unified identity, memory repository, and orchestrator that oversees them.

```
                 SHIVAI IDENTITY (v1.0.0)
                       │
             ┌─────────┴─────────┐
             │                   │
        Persistent             Dynamic
        Information            Information
             │                   │
      Personality            Current task
      Core instructions      Conversation
      Behavioral rules       Tool state
      User preferences      Temporary context
      Long-term memory
             │
             └─────────┬─────────┘
                       ↓
                 AI ORCHESTRATOR
                       ↓
                  MODEL ROUTER
                       ↓
             PROVIDER FALLBACK MGR
                       ↓
        [OpenAI / Claude / Gemini / Groq / DeepSeek / Mistral]
```

---

## 2. Layered Breakdown

### Layer 1: Interface Layer
Exposes asynchronous HTTP REST endpoints and Server-Sent Events (SSE) streaming.
- Built with FastAPI for high throughput and non-blocking I/O.
- Independent of any specific front-end (web, desktop, Android, or IoT launcher).

### Layer 2: API Gateway & Security
- **Authentication**: Validates caller credentials (`X-API-Key` or Bearer tokens).
- **Rate Limiting**: Sliding-window rate limiting per client IP to safeguard downstream quota budgets.
- **Request Tracking**: Generates unique `X-Request-ID` across every turn and propagates it through logging and database records.
- **Security Middleware**: Appends strict HSTS, CSP, and framing protection headers.

### Layer 3: Identity & Context Engine
- **Identity Manager**: Generates immutable master system prompts enforcing the ShivAI persona. Prevents the AI from identifying as ChatGPT, Claude, Gemini, etc.
- **Memory Subsystem**: Dual-tier storage:
  - Ephemeral/Conversation history (recent dialogue turns).
  - Long-term semantic facts (user preferences, system rules, explicit memories).
- **Context Builder**: Combines system prompts, memories, and history within the target model's context limit, pruning older turns while safeguarding critical directives.

### Layer 4: AI Orchestrator & Task Classifier
- Detects task type (Coding, Math, Planning, Research, Vision, General).
- Maps task to specialized agents (e.g., CodingAgent, MathAgent).
- Queries the Model Router for qualified, healthy candidate models.

### Layer 5: Model Router & Fallback Handler
- **Capability Matching**: Ensures models satisfy task requirements (reasoning, vision, tools, coding).
- **Health Filtering**: Dynamically excludes providers under active cooldowns (`QUOTA_EXHAUSTED`, `RATE_LIMITED`, `AUTH_FAILED`).
- **Failover Loop**: Attempts candidate models sequentially. If an error occurs, the classifier categorizes the failure, updates database health records, applies cooldowns, and routes to the next candidate transparently.

### Layer 6: Multi-Model Provider Adapters
Standardized adapters implementing `AIProvider`:
- `providers/openai/`
- `providers/anthropic/`
- `providers/gemini/`
- `providers/groq/`
- `providers/deepseek/`
- `providers/mistral/`
- `providers/generic_openai/`

---

## 3. Error Categories & Cooldown Durations

| Error Category | HTTP Triggers | Behavior | Cooldown |
| :--- | :--- | :--- | :--- |
| `AUTH_ERROR` | 401, 403, invalid key | Marked `AUTH_FAILED`, excluded from pool | 3600s (1 hour) |
| `QUOTA_EXCEEDED` | 429 ("quota", "billing") | Marked `QUOTA_EXHAUSTED`, rotates to fallback | 900s (15 min) |
| `RATE_LIMIT` | 429 (standard) | Marked `RATE_LIMITED`, honors `Retry-After` | `Retry-After` or 45s |
| `TIMEOUT` | 408, 504, ReadTimeout | Marked `DEGRADED`, rotates to fallback | 60s |
| `SERVER_ERROR` | 500, 502, 503 | Marked `DEGRADED`, rotates to fallback | 60s |
| `CONTEXT_TOO_LARGE` | 400 (context limit) | Excludes model for oversized context | None (per-request) |
