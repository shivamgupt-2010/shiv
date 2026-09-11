# ShivAI Official Python SDK

The `shivai` Python SDK provides synchronous and asynchronous bindings to interact with the ShivAI AI Backend.

---

## 1. Installation

Install directly from the local repository or build:

```bash
pip install -e F:/cccccccccc/shivai/sdk
```

---

## 2. Quick Start

### Basic Chat

```python
from shivai import ShivAI

# Automatically reads SHIVAI_API_KEY and SHIVAI_BASE_URL from environment if omitted
client = ShivAI(
    api_key="shivai-test-client-key",
    base_url="http://localhost:8000/api/v1"
)

response = client.chat.create("Hello ShivAI, what is your purpose?")
print("ShivAI:", response.content)
print("Model Provider Used:", response.model.provider)
print("Tokens Used:", response.usage.total_tokens)
print("Conversation ID:", response.conversation_id)
```

---

### Real-Time Streaming

```python
from shivai import ShivAI

client = ShivAI()

print("ShivAI: ", end="", flush=True)
for chunk in client.chat.stream("Explain microservices architecture step-by-step."):
    if chunk.delta:
        print(chunk.delta, end="", flush=True)
print()
```

---

### Persistent Memory Operations

ShivAI allows you to store long-term user preferences, facts, and profile information that persist across model rotations and server restarts:

```python
from shivai import ShivAI

client = ShivAI()

# 1. Store a memory fact
client.memory.remember(
    key="tech_stack",
    value="FastAPI, PostgreSQL with asyncpg, and React",
    category="preference",
    importance=0.9
)

# 2. Recall memories
memories = client.memory.recall(query="PostgreSQL")
for m in memories:
    print(f"[{m.category.upper()}] {m.key}: {m.value}")

# 3. Subsequent chat turns automatically inject relevant memories into the context
res = client.chat.create("What database library should we use?")
print(res.content)
```

---

### Asynchronous Client (`AsyncShivAI`)

For high-concurrency applications, use `AsyncShivAI`:

```python
import asyncio
from shivai import AsyncShivAI

async def main():
    client = AsyncShivAI()
    response = await client.chat.create("Write an async task queue in Python.")
    print(response.content)

asyncio.run(main())
```

---

## 3. Error Handling

The SDK exposes structured exceptions for robust production error handling:

```python
from shivai import ShivAI
from shivai.exceptions import AuthenticationError, RateLimitError, ServiceUnavailableError

client = ShivAI()

try:
    response = client.chat.create("Hello")
except AuthenticationError:
    print("Invalid ShivAI API key.")
except RateLimitError as e:
    print(f"Rate limited. Please retry in {e.retry_after} seconds.")
except ServiceUnavailableError:
    print("All underlying AI providers are currently unavailable.")
```
