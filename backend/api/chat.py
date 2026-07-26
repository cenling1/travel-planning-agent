import json
import logging

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from ..auth import resolve_user_context
from ..database import get_db
from ..schemas import TravelRequest, TravelResponse
from ..services.agent_service import TravelAgentService


router = APIRouter(prefix="/chat", tags=["chat"])
logger = logging.getLogger(__name__)


@router.post("", response_model=TravelResponse)
async def chat(
    http_request: Request,
    request: TravelRequest,
    database: Session = Depends(get_db),
) -> TravelResponse:
    try:
        user = resolve_user_context(http_request, request.client_id, database)
        request = request.model_copy(update={"client_id": user.owner_id})
        return await TravelAgentService(database).chat(request)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/stream")
async def chat_stream(
    http_request: Request,
    request: TravelRequest,
    database: Session = Depends(get_db),
) -> StreamingResponse:
    user = resolve_user_context(http_request, request.client_id, database)
    request = request.model_copy(update={"client_id": user.owner_id})
    service = TravelAgentService(database)

    async def events():
        try:
            async for event in service.chat_stream(request):
                yield json.dumps(event, ensure_ascii=False, separators=(",", ":")) + "\n"
        except ValueError as exc:
            yield json.dumps(
                {"type": "error", "message": str(exc)},
                ensure_ascii=False,
                separators=(",", ":"),
            ) + "\n"
        except Exception:
            logger.exception("Streaming chat failed")
            yield json.dumps(
                {"type": "error", "message": "生成旅行方案时发生错误，请稍后重试。"},
                ensure_ascii=False,
                separators=(",", ":"),
            ) + "\n"

    return StreamingResponse(
        events(),
        media_type="application/x-ndjson",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "X-Accel-Buffering": "no",
        },
    )
