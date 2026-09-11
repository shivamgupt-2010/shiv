# Provider Integration Guide

ShivAI supports 6 primary AI providers plus any generic OpenAI-compatible API.

## 1. Provider Credentials

Set the respective environment variable in `.env`:

```bash
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...
GEMINI_API_KEY=AIzaSy...
GROQ_API_KEY=gsk_...
DEEPSEEK_API_KEY=sk-...
MISTRAL_API_KEY=...
GENERIC_OPENAI_API_KEY=...
GENERIC_OPENAI_BASE_URL=https://openrouter.ai/api/v1
```

---

## 2. Adding a New Provider (4 Simple Steps)

Adding a seventh provider does **not** require modifying ShivAI Core. Follow these steps:

### Step 1: Add Credentials to `config/settings.py`
Add the environment variable to `Settings`:
```python
NEW_PROVIDER_API_KEY: Optional[str] = Field(default=None)
```

### Step 2: Create Adapter in `providers/new_provider/adapter.py`
Inherit from `AIProvider` or `BaseOpenAICompatibleProvider`:
```python
from providers.openai.base_openai_compatible import BaseOpenAICompatibleProvider

class NewProvider(BaseOpenAICompatibleProvider):
    def __init__(self, api_key: Optional[str] = None):
        super().__init__(
            provider_name="new_provider",
            api_key=api_key or settings.NEW_PROVIDER_API_KEY,
            base_url="https://api.newprovider.com/v1",
        )
```

### Step 3: Register in `providers/registry.py`
```python
from providers.new_provider import NewProvider

# Inside _register_defaults():
self.register("new_provider", NewProvider)
```

### Step 4: Declare Model in `config/models_config.yaml`
```yaml
- id: new_provider_model_1
  provider: new_provider
  model: model-alpha
  priority: 85
  capabilities:
    reasoning: true
    vision: false
    tools: true
    streaming: true
    coding: true
  context_limit: 64000
  max_output_tokens: 4096
  cost_tier: low
  status: active
```

The Model Router will immediately discover, score, and fail over to the new provider!
