import asyncio
from collections import Counter
from hashlib import sha256
import math
from pathlib import Path
import re
import shutil

from rank_bm25 import BM25Okapi
from sqlalchemy.orm import Session

from ..config import Settings, get_settings
from ..models import DocumentChunk, KnowledgeDocument, new_id
from ..repositories.knowledge import KnowledgeRepository
from ..schemas import Citation
from .document_parser import (
    SUPPORTED_FILE_TYPES,
    infer_heading,
    load_source_documents,
    split_source_documents,
)
from .embeddings import EmbeddingService
from .reranker import HybridReranker, RankedChunk


def tokenize(text: str) -> list[str]:
    compact = re.sub(r"\s+", "", text.lower())
    chinese = re.findall(r"[\u4e00-\u9fff]", compact)
    bigrams = ["".join(chinese[index:index + 2]) for index in range(len(chinese) - 1)]
    words = re.findall(r"[a-z0-9]+", text.lower())
    return chinese + bigrams + words


def cosine_similarity(left: list[float], right: list[float]) -> float:
    dot = sum(a * b for a, b in zip(left, right))
    left_norm = math.sqrt(sum(value * value for value in left))
    right_norm = math.sqrt(sum(value * value for value in right))
    if not left_norm or not right_norm:
        return 0.0
    return max(-1.0, min(1.0, dot / (left_norm * right_norm)))


class KnowledgeService:
    def __init__(
        self,
        database: Session,
        settings: Settings | None = None,
        embeddings: EmbeddingService | None = None,
    ):
        self.database = database
        self.settings = settings or get_settings()
        self.repository = KnowledgeRepository(database)
        self.embeddings = embeddings or EmbeddingService(self.settings)
        self.reranker = HybridReranker()

    async def ingest(self, filename: str, content: bytes) -> KnowledgeDocument:
        safe_name = Path(filename.replace("\\", "/")).name
        if safe_name in {"", ".", ".."}:
            raise ValueError("文件名无效")
        suffix = Path(safe_name).suffix.lower()
        if suffix not in SUPPORTED_FILE_TYPES:
            raise ValueError(f"不支持的文件类型: {suffix or '未知'}")
        if not content:
            raise ValueError("文件内容为空")
        if len(content) > self.settings.max_upload_bytes:
            raise ValueError(
                f"文件超过 {self.settings.max_upload_bytes // (1024 * 1024)}MB 限制"
            )

        content_hash = sha256(content).hexdigest()
        duplicate = self.repository.find_duplicate(safe_name, content_hash)
        if duplicate:
            return duplicate

        storage_dir = self.settings.upload_dir / content_hash[:16]
        storage_dir.mkdir(parents=True, exist_ok=True)
        storage_path = storage_dir / safe_name
        storage_path.write_bytes(content)

        document = self.repository.create_document(
            filename=safe_name,
            file_type=suffix.lstrip("."),
            content_hash=content_hash,
            storage_path=str(storage_path),
        )
        await self._index_document(document)
        return document

    async def reindex(self, document: KnowledgeDocument) -> KnowledgeDocument:
        self.repository.mark_processing(document)
        await self._index_document(document)
        return document

    async def _index_document(self, document: KnowledgeDocument) -> None:
        try:
            source_path = Path(document.storage_path)
            source_documents = await asyncio.to_thread(load_source_documents, source_path)
            split_documents = await asyncio.to_thread(
                split_source_documents,
                source_documents,
                chunk_size=self.settings.chunk_size,
                chunk_overlap=self.settings.chunk_overlap,
            )
            if not split_documents:
                raise ValueError("文档解析后没有可索引内容")

            texts = [item.page_content.strip() for item in split_documents]
            embeddings = await self.embeddings.embed_documents(texts)
            chunks = []
            for index, (item, text, embedding) in enumerate(
                zip(split_documents, texts, embeddings)
            ):
                page = item.metadata.get("page")
                if isinstance(page, int):
                    page += 1
                chunks.append(
                    DocumentChunk(
                        id=new_id(),
                        document_id=document.id,
                        chunk_index=index,
                        source=document.filename,
                        page=page,
                        heading=infer_heading(text),
                        content=text,
                        token_count=max(1, len(text) // 2),
                        embedding=embedding,
                        chunk_metadata={
                            "source": document.filename,
                            "page": page,
                            "file_type": document.file_type,
                        },
                        quality_score=min(1.0, max(0.2, len(text) / self.settings.chunk_size)),
                    )
                )
            self.repository.replace_chunks(document, chunks)
        except Exception as exc:
            self.repository.mark_failed(document, str(exc))
            raise

    def list_documents(self) -> list[KnowledgeDocument]:
        return self.repository.list_documents()

    def get_document(self, document_id: str) -> KnowledgeDocument | None:
        return self.repository.get_document(document_id)

    def delete_document(self, document: KnowledgeDocument) -> None:
        storage_path = Path(document.storage_path)
        storage_dir = storage_path.parent
        self.repository.delete_document(document)
        if storage_dir.exists() and self.settings.upload_dir in storage_dir.parents:
            shutil.rmtree(storage_dir, ignore_errors=True)

    async def search(self, query: str, top_k: int | None = None) -> list[Citation]:
        limit = top_k or self.settings.search_k
        all_chunks = self.repository.all_ready_chunks()
        if not all_chunks:
            return []

        query_embedding = await self.embeddings.embed_query(query)
        if self.settings.is_postgres:
            vector_rows = self.repository.vector_candidates(query_embedding, max(limit * 8, 30))
            vector_scores = {
                chunk.id: max(0.0, 1.0 - distance)
                for chunk, distance in vector_rows
            }
        else:
            vector_scores = {
                chunk.id: max(0.0, cosine_similarity(query_embedding, chunk.embedding))
                for chunk in all_chunks
            }

        corpus_tokens = [tokenize(chunk.content) for chunk in all_chunks]
        query_tokens = tokenize(query)
        bm25 = BM25Okapi(corpus_tokens)
        raw_lexical = list(bm25.get_scores(query_tokens)) if query_tokens else [0.0] * len(all_chunks)
        maximum = max(raw_lexical) if raw_lexical else 0.0
        lexical_scores = {
            chunk.id: (float(score) / maximum if maximum > 0 else 0.0)
            for chunk, score in zip(all_chunks, raw_lexical)
        }

        query_counts = Counter(query_tokens)
        candidates = []
        for chunk in all_chunks:
            chunk_tokens = Counter(tokenize(chunk.content))
            matched = sum((query_counts & chunk_tokens).values())
            coverage = matched / max(1, sum(query_counts.values()))
            candidates.append(
                RankedChunk(
                    chunk=chunk,
                    vector_score=vector_scores.get(chunk.id, 0.0),
                    lexical_score=lexical_scores.get(chunk.id, 0.0),
                    coverage_score=coverage,
                )
            )

        ranked = self.reranker.rerank(candidates)[:limit]
        return [
            Citation(
                index=index,
                source=item.chunk.source,
                page=item.chunk.page,
                chunk_id=item.chunk.id,
                excerpt=item.chunk.content[:320],
                score=round(item.final_score, 4),
            )
            for index, item in enumerate(ranked, 1)
        ]
