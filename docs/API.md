# ShivAI API Reference

Base URL: `http://localhost:8000/api/v1`

All requests should supply `X-API-Key: <your-key>` or `Authorization: Bearer <your-key>`.

---

## 1. Chat Endpoints

### `POST /api/v1/chat`
Submits a message and receives a normalized non-streaming response.

#### Request Body
```json
{
  "message": "Explain how asynchronous event loops work in Python.",
  "conversation_id": "optional-uuid",
  "agent": "coding",
  "preferred_provider": "openai",
  "temperature": 0.7,
  "max_tokens": 4096
}
```

#### Response (HTTP 200)
```json
{
  "request_id": "4de253d3-317f-4d0f-9549-cb215aea1211",
  "assistant": "shivai",
  "content": "An asynchronous event loop is...",
  "model": {
    "provider": "openai",
    "model": "gpt-4o"
  },
  "usage": {
    "input_tokens": 280,
    "output_tokens": 650,
    "total_tokens": 930
  },
  "finish_reason": "stop",
  "latency_ms": 1120.5,
  "metadata": {
    "conversation_id": "c6a1e945-31f0-4660-84cf-8120e8bfa652"
  }
}
```

---

### `POST /api/v1/chat/stream`
Streams the response progressively via Server-Sent Events (SSE).

#### Response Stream Format
```
data: {"request_id": "...", "assistant": "shivai", "delta": "Shiv", "finish_reason": null}

data: {"request_id": "...", "assistant": "shivai", "delta": "AI is ready.", "finish_reason": "stop"}

data: [DONE]
```

---

## 2. Memory Endpoints

### `GET /api/v1/memory`
List or search active long-term memories.
- Query parameters:
  - `query`: string (optional search term)
  - `category`: string (optional category filter)
  - `limit`: integer (default 50)

### `POST /api/v1/memory`
Store a persistent memory fact or preference.
```json
{
  "key": "preferred_database",
  "value": "PostgreSQL with asyncpg and SQLAlchemy 2.0",
  "category": "preference",
  "importance": 0.8
}
```

### `DELETE /api/v1/memory/{id}`
Deactivates/forgets a persistent memory item.

---

## 3. Conversation Endpoints

### `GET /api/v1/conversations`
List conversation threads for caller.

### `GET /api/v1/conversations/{id}`
Fetch conversation metadata and full message turn history.

### `POST /api/v1/conversations`
```json
{
  "title": "Architecture Redesign",
  "system_instruction_override": "Focus strictly on microservices."
}
```

---

## 4. Health & Observability Endpoints

### `GET /api/v1/health`
Returns basic service liveness.

### `GET /api/v1/health/providers`
Returns provider health states (`HEALTHY`, `RATE_LIMITED`, `QUOTA_EXHAUSTED`, `AUTH_FAILED`), error counts, and cooldown timestamps.

### `GET /api/v1/metrics`
Returns global token throughput, request counts, and average latencies.
