from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..database import get_db
from ..schemas import TravelRequest, TravelResponse
from ..services.agent_service import TravelAgentService


router = APIRouter(prefix="/chat", tags=["chat"])


@router.post("", response_model=TravelResponse)
async def chat(
    request: TravelRequest,
    database: Session = Depends(get_db),
) -> TravelResponse:
    try:
        return await TravelAgentService(database).chat(request)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
