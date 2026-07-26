from fastapi import APIRouter, Depends, File, HTTPException, Query, Request, Response, UploadFile
from sqlalchemy.orm import Session

from ..auth import resolve_user_context
from ..database import get_db
from ..schemas import (
    DocumentOut,
    DocumentUploadResponse,
    SearchRequest,
    SearchResponse,
)
from ..services.knowledge_service import KnowledgeService


router = APIRouter(prefix="/documents", tags=["documents"])


@router.get("", response_model=list[DocumentOut])
def list_documents(
    request: Request,
    client_id: str = Query(default="local", min_length=1, max_length=64),
    database: Session = Depends(get_db),
) -> list[DocumentOut]:
    owner_id = resolve_user_context(request, client_id, database).owner_id
    return KnowledgeService(database).list_documents(owner_id)


@router.post("", response_model=DocumentUploadResponse, status_code=201)
async def upload_documents(
    request: Request,
    files: list[UploadFile] = File(...),
    client_id: str = Query(default="local", min_length=1, max_length=64),
    database: Session = Depends(get_db),
) -> DocumentUploadResponse:
    owner_id = resolve_user_context(request, client_id, database).owner_id
    service = KnowledgeService(database)
    documents = []
    for uploaded_file in files:
        try:
            content = await uploaded_file.read()
            documents.append(
                await service.ingest(
                    owner_id,
                    uploaded_file.filename or "uploaded.txt",
                    content,
                )
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except Exception as exc:
            raise HTTPException(
                status_code=500,
                detail=f"导入 {uploaded_file.filename} 失败: {exc}",
            ) from exc
        finally:
            await uploaded_file.close()
    return DocumentUploadResponse(documents=documents)


@router.post("/search", response_model=SearchResponse)
async def search_documents(
    request: Request,
    payload: SearchRequest,
    client_id: str = Query(default="local", min_length=1, max_length=64),
    database: Session = Depends(get_db),
) -> SearchResponse:
    owner_id = resolve_user_context(request, client_id, database).owner_id
    service = KnowledgeService(database)
    citations = await service.search(owner_id, payload.query, payload.top_k)
    return SearchResponse(
        query=payload.query,
        citations=citations,
        embedding_provider=service.embeddings.provider,
    )


@router.post("/{document_id}/reindex", response_model=DocumentOut)
async def reindex_document(
    request: Request,
    document_id: str,
    client_id: str = Query(default="local", min_length=1, max_length=64),
    database: Session = Depends(get_db),
) -> DocumentOut:
    owner_id = resolve_user_context(request, client_id, database).owner_id
    service = KnowledgeService(database)
    document = service.get_document(owner_id, document_id)
    if document is None:
        raise HTTPException(status_code=404, detail="文档不存在")
    try:
        return await service.reindex(document)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"重新索引失败: {exc}") from exc


@router.delete("/{document_id}", status_code=204)
def delete_document(
    request: Request,
    document_id: str,
    client_id: str = Query(default="local", min_length=1, max_length=64),
    database: Session = Depends(get_db),
) -> Response:
    owner_id = resolve_user_context(request, client_id, database).owner_id
    service = KnowledgeService(database)
    document = service.get_document(owner_id, document_id)
    if document is None:
        raise HTTPException(status_code=404, detail="文档不存在")
    service.delete_document(document)
    return Response(status_code=204)
