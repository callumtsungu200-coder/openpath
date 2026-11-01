import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class Settings:
    database_url: str
    redis_url: str
    anthropic_api_key: str | None
    ai_model: str
    ai_max_calls_per_scan: int
    ai_confidence_threshold: float
    auto_verify_confidence: float
    user_agent: str
    apprenticeship_api_key: str | None = None

    @property
    def ai_enabled(self) -> bool:
        return bool(self.anthropic_api_key)


def load_settings() -> Settings:
    return Settings(
        database_url=os.environ.get("DATABASE_URL", ""),
        redis_url=os.environ.get("REDIS_URL", "redis://localhost:6379/0"),
        anthropic_api_key=os.environ.get("ANTHROPIC_API_KEY") or None,
        ai_model=os.environ.get("OPENPATH_AI_MODEL", "claude-opus-5-5"),
        ai_max_calls_per_scan=int(os.environ.get("OPENPATH_AI_MAX_CALLS_PER_SCAN", "10")),
        ai_confidence_threshold=float(os.environ.get("OPENPATH_AI_THRESHOLD", "0.6")),
        auto_verify_confidence=float(os.environ.get("OPENPATH_AUTO_VERIFY", "0.6")),
        user_agent=os.environ.get("OPENPATH_USER_AGENT", "OpenPathBot/0.1"),
        apprenticeship_api_key=os.environ.get("FIND_APPRENTICESHIP_API_KEY") or None,
    )
