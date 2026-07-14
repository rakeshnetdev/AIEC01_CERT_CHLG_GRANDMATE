import os
from functools import lru_cache
from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    stockfish_path: str = "/usr/local/bin/stockfish"
    engine_depth: int = 16
    inaccuracy_cp: int = 50
    mistake_cp: int = 100
    blunder_cp: int = 300
    gemini_api_key: str = "mock_gemini_key"
    openai_api_key: Optional[str] = None
    llm_model: str = "gemini/gemini-3-pro"
    llm_fallback_model: str = "gpt-4o"
    embed_model: str = "text-embedding-3-small"
    qdrant_url: Optional[str] = None
    tavily_api_key: Optional[str] = None
    db_path: str = "coach.db"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

@lru_cache()
def get_settings() -> Settings:
    """
    Get cached settings. Corrects the path of .env if running from the root folder.
    """
    if not os.path.exists(".env") and os.path.exists("backend/.env"):
        return Settings(_env_file="backend/.env")
    return Settings()
