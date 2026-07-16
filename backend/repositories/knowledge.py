from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from ..models import DocumentChunk, KnowledgeDocument


class KnowledgeRepository:
    def __init__(self, database: Session):
        self.database = database

    def find_duplicate(self, filename: str, content_hash: str) -> KnowledgeDocument | None:
        statement = select(KnowledgeDocument).where(
            KnowledgeDocument.filename == filename,
            KnowledgeDocument.content_hash == content_hash,
        )
        return self.database.scalar(statement)

    def create_document(
        self,
        *,
        filename: str,
        file_type: str,
        content_hash: str,
        storage_path: str,
    ) -> KnowledgeDocument:
        document = KnowledgeDocument(
            filename=filename,
            file_type=file_type,
            content_hash=content_hash,
            storage_path=storage_path,
            status="processing",
        )
        self.database.add(document)
        self.database.commit()
        self.database.refresh(document)
        return document

    def list_documents(self) -> list[KnowledgeDocument]:
        statement = select(KnowledgeDocument).order_by(KnowledgeDocument.created_at.desc())
        return list(self.database.scalars(statement))

    def get_document(self, document_id: str) -> KnowledgeDocument | None:
        return self.database.get(KnowledgeDocument, document_id)

    def all_ready_chunks(self, limit: int = 5000) -> list[DocumentChunk]:
        statement = (
            select(DocumentChunk)
            .join(KnowledgeDocument)
            .where(KnowledgeDocument.status == "ready")
            .limit(limit)
        )
        return list(self.database.scalars(statement))

    def vector_candidates(
        self,
        query_embedding: list[float],
        limit: int,
    ) -> list[tuple[DocumentChunk, float]]:
        distance = DocumentChunk.embedding.cosine_distance(query_embedding).label("distance")
        statement = (
            select(DocumentChunk, distance)
            .join(KnowledgeDocument)
            .where(KnowledgeDocument.status == "ready")
            .order_by(distance)
            .limit(limit)
        )
        return [(chunk, float(value)) for chunk, value in self.database.execute(statement)]

    def replace_chunks(
        self,
        document: KnowledgeDocument,
        chunks: list[DocumentChunk],
    ) -> None:
        self.database.execute(
            delete(DocumentChunk).where(DocumentChunk.document_id == document.id)
        )
        self.database.add_all(chunks)
        document.chunk_count = len(chunks)
        document.status = "ready"
        document.error_message = None
        self.database.commit()
        self.database.refresh(document)

    def mark_failed(self, document: KnowledgeDocument, error_message: str) -> None:
        document.status = "failed"
        document.error_message = error_message[:2000]
        self.database.commit()
        self.database.refresh(document)

    def mark_processing(self, document: KnowledgeDocument) -> None:
        document.status = "processing"
        document.error_message = None
        self.database.commit()

    def delete_document(self, document: KnowledgeDocument) -> None:
        self.database.delete(document)
        self.database.commit()
