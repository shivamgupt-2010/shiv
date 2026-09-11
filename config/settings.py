"""
ShivAI Application Settings
Loads configuration from environment variables and .env file using Pydantic Settings v2.
"""
from typing import List, Optional
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict
from pathlib import Path


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

    # Server Settings
    SHIVAI_ENV: str = "development"
    SHIVAI_PORT: int = 8000
    PORT: Optional[int] = None  # Injected by cloud hosts like Render / Railway
    SHIVAI_HOST: str = "0.0.0.0"
    SHIVAI_DEBUG: bool = False
    SHIVAI_API_KEY: str = "shivai-master-dev-key-change-in-production"
    SHIVAI_ALLOWED_ORIGINS: str = "*"

    @property
    def effective_port(self) -> int:
        return self.PORT or self.SHIVAI_PORT

    # Database
    DATABASE_URL: str = "sqlite+aiosqlite:///./shivai.db"

    # Security & Rate Limiting
    RATE_LIMIT_PER_MINUTE: int = 60
    RATE_LIMIT_BURST: int = 15
    REQUEST_TIMEOUT_SECONDS: float = 60.0

    # Provider API Keys (Secrets - Loaded safely from env)
    OPENAI_API_KEY: Optional[str] = Field(default=None)
    ANTHROPIC_API_KEY: Optional[str] = Field(default=None)
    GEMINI_API_KEY: Optional[str] = Field(default=None)
    GROQ_API_KEY: Optional[str] = Field(default=None)
    GROQ_API_KEY_2: Optional[str] = Field(default=None)
    GROQ_API_KEYS: Optional[str] = Field(default=None)
    DEEPSEEK_API_KEY: Optional[str] = Field(default=None)
    MISTRAL_API_KEY: Optional[str] = Field(default=None)

    # Generic OpenAI-compatible Provider (e.g. OpenRouter, Perplexity, Ollama)
    GENERIC_OPENAI_API_KEY: Optional[str] = Field(default=None)
    GENERIC_OPENAI_BASE_URL: Optional[str] = Field(default=None)

    # Logging & Observability
    LOG_LEVEL: str = "INFO"
    LOG_FORMAT: str = "json"  # json or text
    REDACT_SECRETS: bool = True

    # Paths
    BASE_DIR: Path = Path(__file__).resolve().parent.parent
    CONFIG_DIR: Path = BASE_DIR / "config"
    MODELS_CONFIG_PATH: Path = CONFIG_DIR / "models_config.yaml"

    @property
    def cors_origins(self) -> List[str]:
        if self.SHIVAI_ALLOWED_ORIGINS == "*":
            return ["*"]
        return [origin.strip() for origin in self.SHIVAI_ALLOWED_ORIGINS.split(",") if origin.strip()]

    def get_configured_providers(self) -> List[str]:
        """Returns the list of providers that have an API key configured."""
        providers = []
        if self.OPENAI_API_KEY:
            providers.append("openai")
        if self.ANTHROPIC_API_KEY:
            providers.append("anthropic")
        if self.GEMINI_API_KEY:
            providers.append("gemini")
        if self.GROQ_API_KEY or self.GROQ_API_KEY_2 or self.GROQ_API_KEYS:
            providers.append("groq")
        if self.DEEPSEEK_API_KEY:
            providers.append("deepseek")
        if self.MISTRAL_API_KEY:
            providers.append("mistral")
        if self.GENERIC_OPENAI_API_KEY:
            providers.append("generic_openai")
        return providers

    def get_groq_keys(self) -> List[str]:
        """Returns all configured Groq keys for pooling and rotation."""
        keys = []
        if self.GROQ_API_KEY:
            keys.append(self.GROQ_API_KEY)
        if self.GROQ_API_KEY_2 and self.GROQ_API_KEY_2 not in keys:
            keys.append(self.GROQ_API_KEY_2)
        if self.GROQ_API_KEYS:
            for k in self.GROQ_API_KEYS.split(","):
                k = k.strip()
                if k and k not in keys:
                    keys.append(k)
        return keys

    def get_secret_keys_for_redaction(self) -> List[str]:
        """Returns non-empty secrets to be masked in log streams."""
        secrets = [
            self.SHIVAI_API_KEY,
            self.OPENAI_API_KEY,
            self.ANTHROPIC_API_KEY,
            self.GEMINI_API_KEY,
            self.GROQ_API_KEY,
            self.GROQ_API_KEY_2,
            self.DEEPSEEK_API_KEY,
            self.MISTRAL_API_KEY,
            self.GENERIC_OPENAI_API_KEY,
        ]
        if self.GROQ_API_KEYS:
            secrets.extend(self.get_groq_keys())
        return [s for s in secrets if s and len(s.strip()) > 3]


settings = Settings()
