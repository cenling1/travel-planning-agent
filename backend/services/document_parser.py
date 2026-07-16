from pathlib import Path

from langchain_community.document_loaders import CSVLoader, PyPDFLoader, TextLoader
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter


SUPPORTED_FILE_TYPES = {".txt", ".md", ".pdf", ".csv"}


def load_source_documents(path: Path) -> list[Document]:
    suffix = path.suffix.lower()
    if suffix not in SUPPORTED_FILE_TYPES:
        raise ValueError(f"不支持的文件类型: {suffix or '未知'}")

    if suffix in {".txt", ".md"}:
        loader = TextLoader(str(path), encoding="utf-8")
    elif suffix == ".pdf":
        loader = PyPDFLoader(str(path))
    else:
        loader = CSVLoader(str(path), encoding="utf-8")

    return loader.load()


def split_source_documents(
    documents: list[Document],
    *,
    chunk_size: int,
    chunk_overlap: int,
) -> list[Document]:
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        separators=["\n## ", "\n### ", "\n\n", "\n", "。", "！", "？", " ", ""],
    )
    return splitter.split_documents(documents)


def infer_heading(content: str) -> str | None:
    for line in content.splitlines():
        candidate = line.strip().lstrip("#").strip()
        if candidate and len(candidate) <= 80:
            return candidate
    return None
