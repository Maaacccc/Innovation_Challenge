from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache


@dataclass(frozen=True)
class Settings:
    app_name: str = "Eldercare Multi-Agent Coordination Prototype"
    api_prefix: str = "/api"
    database_url: str = os.getenv(
        "DATABASE_URL",
        "postgresql+psycopg://postgres:postgres@localhost:5432/eldercare",
    )
    jwt_secret: str = os.getenv("JWT_SECRET", "development-secret")
    access_token_expire_minutes: int = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "60"))
    refresh_token_expire_minutes: int = int(
        os.getenv("REFRESH_TOKEN_EXPIRE_MINUTES", str(60 * 24 * 7))
    )
    openai_api_key: str | None = os.getenv("OPENAI_API_KEY")
    openai_base_url: str | None = os.getenv("OPENAI_BASE_URL")
    openai_task_model: str = os.getenv("OPENAI_TASK_MODEL", "gpt-5-mini")
    openai_risk_model: str = os.getenv("OPENAI_RISK_MODEL", "gpt-5.2")
    openai_enable_live: bool = os.getenv("OPENAI_ENABLE_LIVE", "false").lower() == "true"
    max_review_rounds: int = int(os.getenv("MAX_REVIEW_ROUNDS", "3"))
    frontend_origin: str = os.getenv("FRONTEND_ORIGIN", "http://localhost:5173")
    local_db_url: str = "sqlite+pysqlite:///./eldercare.db"

    @property
    def normalized_database_url(self) -> str:
        return self.database_url or self.local_db_url

    @property
    def is_sqlite(self) -> bool:
        return self.normalized_database_url.startswith("sqlite")


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()

