from __future__ import annotations

import json
from pathlib import Path
from typing import List, Union
from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings for GenAI Event Planner backend."""

    # Groq API Configuration (Free tier: https://console.groq.com)
    groq_api_key: str = ""
    groq_model: str = "openai/gpt-oss-120b"


    # Server Settings
    host: str = "0.0.0.0"
    port: int = 8000
    debug: bool = False

    # State Storage Path (Keyed by session_id in state/)
    state_dir: Path = Path("state")

    # CORS Settings
    cors_origins: Union[List[str], str] = ["http://localhost:5173", "http://127.0.0.1:5173"]

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_cors_origins(cls, value: Union[str, List[str]]) -> List[str]:
        if isinstance(value, str):
            value = value.strip()
            if value.startswith("[") and value.endswith("]"):
                try:
                    parsed = json.loads(value)
                    if isinstance(parsed, list):
                        return [str(item).strip() for item in parsed]
                except Exception:
                    pass
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        return value

    @field_validator("state_dir", mode="after")
    @classmethod
    def ensure_state_dir(cls, value: Path) -> Path:
        resolved_path = value.resolve()
        resolved_path.mkdir(parents=True, exist_ok=True)
        return resolved_path


settings = Settings()

