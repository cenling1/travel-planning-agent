from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from sqlalchemy.orm import Session

from ..auth import resolve_user_context
from ..database import get_db
from ..repositories.conversations import ConversationRepository
from ..schemas import ConversationCreate, ConversationDetail, ConversationOut


router = APIRouter(prefix="/conversations", tags=["conversations"])


@router.post("", response_model=ConversationOut, status_code=201)
def create_conversation(
    request: Request,
    payload: ConversationCreate,
    database: Session = Depends(get_db),
) -> ConversationOut:
    owner_id = resolve_user_context(request, payload.client_id, database).owner_id
    return ConversationRepository(database).create(owner_id, payload.title)


@router.get("", response_model=list[ConversationOut])
def list_conversations(
    request: Request,
    client_id: str = Query(default="local", min_length=1, max_length=64),
    database: Session = Depends(get_db),
) -> list[ConversationOut]:
    owner_id = resolve_user_context(request, client_id, database).owner_id
    return ConversationRepository(database).list(owner_id)


@router.get("/{conversation_id}", response_model=ConversationDetail)
def get_conversation(
    request: Request,
    conversation_id: str,
    client_id: str = Query(default="local", min_length=1, max_length=64),
    database: Session = Depends(get_db),
) -> ConversationDetail:
    owner_id = resolve_user_context(request, client_id, database).owner_id
    conversation = ConversationRepository(database).get_with_messages(
        conversation_id,
        owner_id,
    )
    if conversation is None:
        raise HTTPException(status_code=404, detail="会话不存在")
    return conversation


@router.delete("/{conversation_id}", status_code=204)
def delete_conversation(
    request: Request,
    conversation_id: str,
    client_id: str = Query(default="local", min_length=1, max_length=64),
    database: Session = Depends(get_db),
) -> Response:
    owner_id = resolve_user_context(request, client_id, database).owner_id
    repository = ConversationRepository(database)
    conversation = repository.get(conversation_id, owner_id)
    if conversation is None:
        raise HTTPException(status_code=404, detail="会话不存在")
    repository.delete(conversation)
    return Response(status_code=204)
