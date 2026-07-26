from dataclasses import dataclass
from functools import lru_cache
import os
from pathlib import Path

from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_ROOT = PROJECT_ROOT / "data"

root_env = PROJECT_ROOT / ".env"
if root_env.exists():
    load_dotenv(root_env, override=False)


def _default_database_url() -> str:
    database_path = DATA_ROOT / "travel_agent.db"
    return f"sqlite:///{database_path.as_posix()}"


@dataclass(frozen=True)
class Settings:
    app_name: str = "Travel planning agent API"
    api_prefix: str = "/api"
    database_url: str = os.getenv("DATABASE_URL", _default_database_url())
    upload_dir: Path = Path(
        os.getenv("UPLOAD_DIR", str(DATA_ROOT / "uploads"))
    )
    mcp_config_path: Path = Path(
        os.getenv("MCP_CONFIG_PATH", str(PROJECT_ROOT / "config" / "servers_config.json"))
    )
    dashscope_api_key: str = os.getenv("DASHSCOPE_API_KEY", "")
    deepseek_api_key: str = os.getenv("DEEPSEEK_API_KEY", "")
    deepseek_chat_model: str = os.getenv("DEEPSEEK_CHAT_MODEL", "deepseek-v4-pro")
    deepseek_reasoning_model: str = os.getenv(
        "DEEPSEEK_REASONING_MODEL", "deepseek-v4-pro"
    )
    deepseek_base_url: str = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
    deepseek_temperature: float = float(os.getenv("DEEPSEEK_TEMPERATURE", "0.7"))
    deepseek_thinking_enabled: bool = (
        os.getenv("DEEPSEEK_THINKING_ENABLED", "false").lower() == "true"
    )
    llm_extraction_timeout_seconds: float = float(
        os.getenv("LLM_EXTRACTION_TIMEOUT_SECONDS", "12")
    )
    llm_generation_timeout_seconds: float = float(
        os.getenv("LLM_GENERATION_TIMEOUT_SECONDS", "75")
    )
    rag_timeout_seconds: float = float(os.getenv("RAG_TIMEOUT_SECONDS", "12"))
    mcp_timeout_seconds: float = float(os.getenv("MCP_TIMEOUT_SECONDS", "30"))
    agent_max_rounds: int = int(os.getenv("AGENT_MAX_ROUNDS", "3"))
    agent_max_tool_calls: int = int(os.getenv("AGENT_MAX_TOOL_CALLS", "12"))
    embedding_model: str = os.getenv("EMBEDDING_MODEL", "text-embedding-v4")
    embedding_dimension: int = int(os.getenv("EMBEDDING_DIMENSION", "1024"))
    chunk_size: int = int(os.getenv("RAG_CHUNK_SIZE", "500"))
    chunk_overlap: int = int(os.getenv("RAG_CHUNK_OVERLAP", "50"))
    search_k: int = int(os.getenv("RAG_SEARCH_K", "5"))
    max_upload_bytes: int = int(os.getenv("MAX_UPLOAD_BYTES", str(20 * 1024 * 1024)))
    auth_enabled: bool = os.getenv("AUTH_ENABLED", "false").lower() == "true"
    auth_registration_enabled: bool = (
        os.getenv("AUTH_REGISTRATION_ENABLED", "true").lower() == "true"
    )
    jwt_secret: str = os.getenv("JWT_SECRET", "")
    jwt_issuer: str = os.getenv("JWT_ISSUER", "travel-planning-agent")
    jwt_audience: str = os.getenv("JWT_AUDIENCE", "travel-planning-agent-web")
    jwt_access_minutes: int = int(os.getenv("JWT_ACCESS_MINUTES", "15"))
    jwt_refresh_days: int = int(os.getenv("JWT_REFRESH_DAYS", "30"))
    bootstrap_admin_username: str = os.getenv("BOOTSTRAP_ADMIN_USERNAME", "")
    bootstrap_admin_password: str = os.getenv("BOOTSTRAP_ADMIN_PASSWORD", "")
    rate_limit_per_minute: int = int(os.getenv("RATE_LIMIT_PER_MINUTE", "0"))
    max_inflight_requests: int = int(os.getenv("MAX_INFLIGHT_REQUESTS", "0"))
    cors_origins: tuple[str, ...] = tuple(
        origin.strip()
        for origin in os.getenv(
            "CORS_ORIGINS",
            "http://localhost:5173",
        ).split(",")
        if origin.strip()
    )
    cookie_secure: bool = os.getenv("COOKIE_SECURE", "false").lower() == "true"
    cookie_domain: str = os.getenv("COOKIE_DOMAIN", "")

    @property
    def is_postgres(self) -> bool:
        return self.database_url.startswith(("postgresql://", "postgresql+psycopg://"))


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    settings = Settings()
    settings.upload_dir.mkdir(parents=True, exist_ok=True)
    return settings


def validate_security_settings(settings: Settings) -> None:
    if not settings.auth_enabled:
        return
    if len(settings.jwt_secret) < 32:
        raise RuntimeError("JWT_SECRET must contain at least 32 characters when AUTH_ENABLED=true")
    if settings.jwt_access_minutes < 1 or settings.jwt_refresh_days < 1:
        raise RuntimeError("JWT token lifetimes must be positive")
    if bool(settings.bootstrap_admin_username) != bool(settings.bootstrap_admin_password):
        raise RuntimeError(
            "BOOTSTRAP_ADMIN_USERNAME and BOOTSTRAP_ADMIN_PASSWORD must be set together"
        )
