import argparse
import json
from pathlib import Path

import httpx


def evaluate(api_url: str, dataset_path: Path, top_k: int) -> dict:
    questions = json.loads(dataset_path.read_text(encoding="utf-8"))
    reciprocal_ranks = []
    source_hits = 0
    term_coverages = []

    with httpx.Client(
        base_url=api_url.rstrip("/"),
        timeout=60,
        trust_env=False,
    ) as client:
        for item in questions:
            response = client.post(
                "/api/documents/search",
                json={"query": item["query"], "top_k": top_k},
            )
            response.raise_for_status()
            citations = response.json()["citations"]
            expected_sources = set(item.get("expected_sources", []))
            rank = next(
                (
                    index
                    for index, citation in enumerate(citations, 1)
                    if citation["source"] in expected_sources
                ),
                None,
            )
            reciprocal_ranks.append(1 / rank if rank else 0.0)
            source_hits += int(rank is not None)

            retrieved_text = " ".join(citation["excerpt"] for citation in citations)
            expected_terms = item.get("expected_terms", [])
            matched_terms = sum(term in retrieved_text for term in expected_terms)
            term_coverages.append(matched_terms / max(1, len(expected_terms)))

    total = max(1, len(questions))
    return {
        "questions": len(questions),
        f"source_recall@{top_k}": round(source_hits / total, 4),
        "mrr": round(sum(reciprocal_ranks) / total, 4),
        "expected_term_coverage": round(sum(term_coverages) / total, 4),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate hybrid RAG retrieval")
    parser.add_argument("--api-url", default="http://localhost:8000")
    parser.add_argument(
        "--dataset",
        type=Path,
        default=Path("evaluation/rag_questions.json"),
    )
    parser.add_argument("--top-k", type=int, default=5)
    args = parser.parse_args()
    print(json.dumps(evaluate(args.api_url, args.dataset, args.top_k), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
