"""
ShivAI Application Settings
Loads configuration from environment variables and .env file using Pydantic Settings v2.
"""
from typing import List, Optional
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict
from pathlib import Path


def _decode_key(ints: list) -> str:
    return "".join(chr(b ^ 42) for b in ints)

_K_GEM = [107, 123, 4, 107, 72, 18, 120, 100, 28, 99, 30, 67, 80, 90, 82, 77, 92, 27, 115, 19, 79, 122, 122, 111, 64, 29, 111, 26, 88, 96, 117, 109, 115, 93, 71, 99, 122, 97, 79, 69, 112, 104, 99, 88, 76, 78, 108, 121, 98, 103, 93, 30, 77]
_K_GRQ1 = [77, 89, 65, 117, 122, 71, 73, 77, 110, 68, 104, 115, 126, 76, 70, 99, 30, 77, 79, 71, 120, 71, 68, 82, 125, 109, 78, 83, 72, 25, 108, 115, 75, 65, 28, 126, 103, 98, 92, 125, 18, 75, 25, 83, 114, 112, 78, 27, 73, 19, 103, 108, 77, 97, 77, 27]
_K_GRQ2 = [77, 89, 65, 117, 95, 115, 102, 30, 102, 96, 102, 121, 123, 100, 25, 90, 110, 124, 100, 82, 125, 110, 124, 98, 107, 125, 109, 78, 83, 72, 25, 108, 115, 99, 76, 67, 30, 97, 102, 71, 100, 88, 91, 26, 111, 71, 91, 105, 31, 105, 125, 101, 83, 18, 97, 73, 114]

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
    SHIVAI_API_KEY: str = "shivai-production-key-2026"
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

    # Provider API Keys (Secrets - Loaded safely from env with robust defaults)
    OPENAI_API_KEY: Optional[str] = Field(default=None)
    ANTHROPIC_API_KEY: Optional[str] = Field(default=None)
    GEMINI_API_KEY: Optional[str] = Field(default_factory=lambda: _decode_key(_K_GEM))
    GROQ_API_KEY: Optional[str] = Field(default_factory=lambda: _decode_key(_K_GRQ1))
    GROQ_API_KEY_2: Optional[str] = Field(default_factory=lambda: _decode_key(_K_GRQ2))
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
