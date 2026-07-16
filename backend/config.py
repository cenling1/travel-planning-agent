from dataclasses import dataclass
from functools import lru_cache
import os
from pathlib import Path

from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parent.parent
PACKAGE_ROOT = PROJECT_ROOT / "aggentic_RAG"

package_env = PACKAGE_ROOT / ".env"
root_env = PROJECT_ROOT / ".env"
if package_env.exists():
    load_dotenv(package_env, override=False)
elif root_env.exists():
    load_dotenv(root_env, override=False)


def _default_database_url() -> str:
    database_path = PACKAGE_ROOT / "data" / "travel_agent.db"
    return f"sqlite:///{database_path.as_posix()}"


@dataclass(frozen=True)
class Settings:
    app_name: str = "Travel planning agent API"
    api_prefix: str = "/api"
    database_url: str = os.getenv("DATABASE_URL", _default_database_url())
    upload_dir: Path = Path(
        os.getenv("UPLOAD_DIR", str(PACKAGE_ROOT / "data" / "uploads"))
    )
    dashscope_api_key: str = os.getenv("DASHSCOPE_API_KEY", "")
    deepseek_api_key: str = os.getenv("DEEPSEEK_API_KEY", "")
    qwen_model: str = os.getenv("QWEN_MODEL", "qwen-plus")
    embedding_model: str = os.getenv("EMBEDDING_MODEL", "text-embedding-v4")
    embedding_dimension: int = int(os.getenv("EMBEDDING_DIMENSION", "1024"))
    chunk_size: int = int(os.getenv("RAG_CHUNK_SIZE", "500"))
    chunk_overlap: int = int(os.getenv("RAG_CHUNK_OVERLAP", "50"))
    search_k: int = int(os.getenv("RAG_SEARCH_K", "5"))
    max_upload_bytes: int = int(os.getenv("MAX_UPLOAD_BYTES", str(20 * 1024 * 1024)))
    cors_origins: tuple[str, ...] = tuple(
        origin.strip()
        for origin in os.getenv(
            "CORS_ORIGINS",
            "http://localhost:8501,http://localhost:8502",
        ).split(",")
        if origin.strip()
    )

    @property
    def is_postgres(self) -> bool:
        return self.database_url.startswith(("postgresql://", "postgresql+psycopg://"))


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    settings = Settings()
    settings.upload_dir.mkdir(parents=True, exist_ok=True)
    return settings
