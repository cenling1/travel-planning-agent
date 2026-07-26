from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from sqlalchemy.orm import Session

from ..auth import resolve_user_context
from ..database import get_db
from ..schemas import MemoryCreate, MemoryOut
from ..services.memory_service import MemoryService


router = APIRouter(prefix="/memories", tags=["memories"])


@router.get("", response_model=list[MemoryOut])
def list_memories(
    request: Request,
    client_id: str = Query(default="local", min_length=1, max_length=64),
    database: Session = Depends(get_db),
) -> list[MemoryOut]:
    owner_id = resolve_user_context(request, client_id, database).owner_id
    return MemoryService(database).list_memories(owner_id)


@router.post("", response_model=MemoryOut, status_code=201)
def remember(
    request: Request,
    payload: MemoryCreate,
    client_id: str = Query(default="local", min_length=1, max_length=64),
    database: Session = Depends(get_db),
) -> MemoryOut:
    owner_id = resolve_user_context(request, client_id, database).owner_id
    return MemoryService(database).remember(
        owner_id=owner_id,
        memory_key=payload.memory_key,
        content=payload.content,
        memory_type=payload.memory_type,
        importance=payload.importance,
    )


@router.delete("/{memory_id}", status_code=204)
def forget(
    request: Request,
    memory_id: str,
    client_id: str = Query(default="local", min_length=1, max_length=64),
    database: Session = Depends(get_db),
) -> Response:
    owner_id = resolve_user_context(request, client_id, database).owner_id
    deleted = MemoryService(database).forget(owner_id, memory_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="记忆不存在")
    return Response(status_code=204)
