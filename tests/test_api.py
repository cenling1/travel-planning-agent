import unittest

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from backend.database import Base, get_db
from backend.main import app


class ApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(cls.engine)
        cls.database = Session(cls.engine)

        def override_database():
            yield cls.database

        app.dependency_overrides[get_db] = override_database
        cls.client = TestClient(app)

    @classmethod
    def tearDownClass(cls):
        app.dependency_overrides.clear()
        cls.client.close()
        cls.database.close()
        cls.engine.dispose()

    def test_health_and_openapi_include_business_routes(self):
        health = self.client.get("/health")
        self.assertEqual(health.status_code, 200)
        paths = self.client.get("/openapi.json").json()["paths"]
        self.assertIn("/api/chat", paths)
        self.assertIn("/api/documents/search", paths)

    def test_conversation_crud(self):
        created = self.client.post(
            "/api/conversations",
            json={"client_id": "api-test", "title": "成都旅行"},
        )
        self.assertEqual(created.status_code, 201)
        conversation_id = created.json()["id"]

        listed = self.client.get(
            "/api/conversations",
            params={"client_id": "api-test"},
        )
        self.assertEqual([item["id"] for item in listed.json()], [conversation_id])

        detail = self.client.get(
            f"/api/conversations/{conversation_id}",
            params={"client_id": "api-test"},
        )
        self.assertEqual(detail.status_code, 200)
        self.assertEqual(detail.json()["messages"], [])

        deleted = self.client.delete(
            f"/api/conversations/{conversation_id}",
            params={"client_id": "api-test"},
        )
        self.assertEqual(deleted.status_code, 204)

    def test_document_validation_and_empty_search(self):
        invalid = self.client.post(
            "/api/documents",
            files={"files": ("malware.exe", b"invalid", "application/octet-stream")},
        )
        self.assertEqual(invalid.status_code, 400)

        search = self.client.post(
            "/api/documents/search",
            json={"query": "成都熊猫", "top_k": 3},
        )
        self.assertEqual(search.status_code, 200)
        self.assertEqual(search.json()["citations"], [])


if __name__ == "__main__":
    unittest.main()
