from dataclasses import dataclass

from ..models import DocumentChunk


@dataclass
class RankedChunk:
    chunk: DocumentChunk
    vector_score: float
    lexical_score: float
    coverage_score: float
    final_score: float = 0.0


class HybridReranker:
    """Lightweight reranker combining semantic, lexical and query coverage signals."""

    def rerank(self, candidates: list[RankedChunk]) -> list[RankedChunk]:
        for candidate in candidates:
            heading_boost = 0.03 if candidate.chunk.heading else 0.0
            quality = max(0.0, min(candidate.chunk.quality_score, 1.0))
            candidate.final_score = (
                0.52 * candidate.vector_score
                + 0.33 * candidate.lexical_score
                + 0.10 * candidate.coverage_score
                + 0.05 * quality
                + heading_boost
            )
        return sorted(candidates, key=lambda item: item.final_score, reverse=True)
