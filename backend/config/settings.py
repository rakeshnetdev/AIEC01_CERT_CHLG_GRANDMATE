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
    chroma_db_path: str = "data/chroma"
    retriever_type: str = "hybrid"

    # LangSmith Tracing
    langchain_tracing_v2: str = "false"
    langchain_api_key: Optional[str] = None
    langsmith_api_key: Optional[str] = None
    langchain_project: str = "grandmate"
    langchain_endpoint: str = "https://api.smith.langchain.com"

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
        s = Settings(_env_file="backend/.env")
    else:
        s = Settings()

    # Populate LangChain environment variables to enable automatic tracing in LangGraph/LangChain
    api_key = s.langchain_api_key or s.langsmith_api_key or os.environ.get("LANGSMITH_API_KEY") or os.environ.get("LANGCHAIN_API_KEY")
    if api_key:
        os.environ["LANGCHAIN_TRACING_V2"] = s.langchain_tracing_v2
        os.environ["LANGCHAIN_API_KEY"] = api_key
        os.environ["LANGCHAIN_PROJECT"] = s.langchain_project
        os.environ["LANGCHAIN_ENDPOINT"] = s.langchain_endpoint

    return s
