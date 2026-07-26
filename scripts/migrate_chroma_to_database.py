import argparse
import asyncio
from collections import defaultdict
from pathlib import Path

import chromadb

from backend.config import get_settings
from backend.database import SessionLocal, init_db
from backend.services.knowledge_service import KnowledgeService


async def migrate(chroma_path: Path) -> None:
    client = chromadb.PersistentClient(path=str(chroma_path))
    try:
        collection = client.get_collection("travel_knowledge")
    except Exception as exc:
        raise SystemExit(f"找不到 travel_knowledge 集合: {exc}") from exc

    data = collection.get(include=["documents", "metadatas"])
    grouped: dict[str, list[str]] = defaultdict(list)
    for content, metadata in zip(data.get("documents", []), data.get("metadatas", [])):
        source = Path((metadata or {}).get("source", "migrated_knowledge.txt")).name
        grouped[source].append(content)

    init_db()
    with SessionLocal() as database:
        service = KnowledgeService(database)
        for source, contents in grouped.items():
            filename = source if Path(source).suffix.lower() in {".txt", ".md"} else f"{source}.txt"
            document = await service.ingest(
                "local",
                filename,
                "\n\n".join(contents).encode("utf-8"),
            )
            print(f"{filename}: {document.status}, {document.chunk_count} chunks")


def main() -> None:
    settings = get_settings()
    parser = argparse.ArgumentParser(description="Migrate Chroma chunks into the new database")
    parser.add_argument(
        "--chroma-path",
        type=Path,
        default=Path("data/legacy_chroma"),
    )
    args = parser.parse_args()
    print(f"database: {settings.database_url}")
    asyncio.run(migrate(args.chroma_path))


if __name__ == "__main__":
    main()
