from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from ..config import get_settings
from ..database import get_db
from ..schemas import HealthResponse
from ..services.embeddings import EmbeddingService
from ..services.mcp_travel_service import mcp_travel_service


router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse)
def health(database: Session = Depends(get_db)) -> HealthResponse:
    database.execute(text("SELECT 1"))
    settings = get_settings()
    return HealthResponse(
        status="ok",
        database="postgresql-pgvector" if settings.is_postgres else "sqlite-fallback",
        embedding_provider=EmbeddingService(settings).provider,
    )


@router.get("/health/tools")
async def tool_health() -> dict:
    return {"configured": await mcp_travel_service.health()}
