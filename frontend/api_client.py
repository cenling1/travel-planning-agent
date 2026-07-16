from typing import Any

import httpx


class TravelApiClient:
    def __init__(self, base_url: str):
        self.base_url = base_url.rstrip("/")
        self.client = httpx.Client(
            base_url=self.base_url,
            timeout=httpx.Timeout(120, connect=5),
            trust_env=False,
        )

    def health(self) -> dict[str, Any]:
        response = self.client.get("/health")
        response.raise_for_status()
        return response.json()

    def chat(
        self,
        *,
        query: str,
        client_id: str,
        conversation_id: str | None,
    ) -> dict[str, Any]:
        response = self.client.post(
            "/api/chat",
            json={
                "query": query,
                "client_id": client_id,
                "conversation_id": conversation_id,
            },
        )
        response.raise_for_status()
        return response.json()

    def list_conversations(self, client_id: str) -> list[dict[str, Any]]:
        response = self.client.get("/api/conversations", params={"client_id": client_id})
        response.raise_for_status()
        return response.json()

    def get_conversation(self, conversation_id: str, client_id: str) -> dict[str, Any]:
        response = self.client.get(
            f"/api/conversations/{conversation_id}",
            params={"client_id": client_id},
        )
        response.raise_for_status()
        return response.json()

    def delete_conversation(self, conversation_id: str, client_id: str) -> None:
        response = self.client.delete(
            f"/api/conversations/{conversation_id}",
            params={"client_id": client_id},
        )
        response.raise_for_status()

    def list_documents(self) -> list[dict[str, Any]]:
        response = self.client.get("/api/documents")
        response.raise_for_status()
        return response.json()

    def upload_documents(self, uploaded_files) -> list[dict[str, Any]]:
        files = [
            (
                "files",
                (uploaded_file.name, uploaded_file.getvalue(), uploaded_file.type),
            )
            for uploaded_file in uploaded_files
        ]
        response = self.client.post("/api/documents", files=files)
        response.raise_for_status()
        return response.json()["documents"]

    def reindex_document(self, document_id: str) -> dict[str, Any]:
        response = self.client.post(f"/api/documents/{document_id}/reindex")
        response.raise_for_status()
        return response.json()

    def delete_document(self, document_id: str) -> None:
        response = self.client.delete(f"/api/documents/{document_id}")
        response.raise_for_status()
