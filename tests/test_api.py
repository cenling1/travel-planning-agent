import json
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from backend.auth import AuthService
from backend.config import Settings, get_settings
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
        self.assertIn("/api/chat/stream", paths)
        self.assertIn("/api/documents/search", paths)
        self.assertIn("/api/memories", paths)
        self.assertIn("/api/auth/login", paths)
        self.assertIn("/api/admin/users", paths)

    def test_chat_stream_returns_ndjson_events(self):
        async def fake_stream(_service, _request):
            yield {"type": "status", "message": "正在处理"}
            yield {"type": "delta", "content": "上海"}
            yield {
                "type": "complete",
                "response": {
                    "conversation_id": "stream-test",
                    "answer": "上海",
                    "citations": [],
                    "tools": [],
                    "scenario_type": "simple",
                    "retrieved_chunks": 0,
                },
            }

        with patch(
            "backend.api.chat.TravelAgentService.chat_stream",
            new=fake_stream,
        ):
            response = self.client.post(
                "/api/chat/stream",
                json={"query": "规划上海旅行", "client_id": "stream-client"},
            )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.headers["content-type"].startswith("application/x-ndjson"))
        events = [json.loads(line) for line in response.text.splitlines()]
        self.assertEqual([event["type"] for event in events], ["status", "delta", "complete"])

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
            params={"client_id": "api-test"},
            json={"query": "成都熊猫", "top_k": 3},
        )
        self.assertEqual(search.status_code, 200)
        self.assertEqual(search.json()["citations"], [])

    def test_memory_crud_is_scoped_by_client_id(self):
        created = self.client.post(
            "/api/memories",
            params={"client_id": "api-memory-a"},
            json={"memory_key": "偏好", "content": "喜欢慢节奏旅行"},
        )
        self.assertEqual(created.status_code, 201)
        memory_id = created.json()["id"]

        own = self.client.get("/api/memories", params={"client_id": "api-memory-a"})
        other = self.client.get("/api/memories", params={"client_id": "api-memory-b"})
        self.assertEqual([item["id"] for item in own.json()], [memory_id])
        self.assertEqual(other.json(), [])

        forbidden_delete = self.client.delete(
            f"/api/memories/{memory_id}",
            params={"client_id": "api-memory-b"},
        )
        self.assertEqual(forbidden_delete.status_code, 404)

        deleted = self.client.delete(
            f"/api/memories/{memory_id}",
            params={"client_id": "api-memory-a"},
        )
        self.assertEqual(deleted.status_code, 204)

    def test_jwt_identity_overrides_spoofed_client_id_and_enforces_admin_role(self):
        settings = Settings(
            auth_enabled=True,
            auth_registration_enabled=True,
            jwt_secret="test-secret-that-is-longer-than-thirty-two-characters",
            jwt_access_minutes=15,
            jwt_refresh_days=30,
        )
        app.dependency_overrides[get_settings] = lambda: settings
        try:
            with patch("backend.auth.get_settings", return_value=settings):
                alice = self.client.post(
                    "/api/auth/register",
                    json={"username": "jwt-alice", "password": "StrongPass1!"},
                )
                bob = self.client.post(
                    "/api/auth/register",
                    json={"username": "jwt-bob", "password": "StrongPass1!"},
                )
                self.assertEqual(alice.status_code, 201)
                self.assertEqual(bob.status_code, 201)
                alice_token = alice.json()["access_token"]
                bob_token = bob.json()["access_token"]

                created = self.client.post(
                    "/api/conversations",
                    headers={"Authorization": f"Bearer {alice_token}"},
                    json={"client_id": "jwt-bob", "title": "JWT scoped"},
                )
                self.assertEqual(created.status_code, 201)
                conversation_id = created.json()["id"]
                bob_list = self.client.get(
                    "/api/conversations",
                    headers={"Authorization": f"Bearer {bob_token}"},
                    params={"client_id": "jwt-alice"},
                )
                self.assertNotIn(conversation_id, [item["id"] for item in bob_list.json()])
                self.assertEqual(self.client.get("/api/conversations").status_code, 401)
                self.assertEqual(
                    self.client.get(
                        "/api/admin/users",
                        headers={"Authorization": f"Bearer {alice_token}"},
                    ).status_code,
                    403,
                )

                AuthService(self.database, settings).create_user(
                    "jwt-admin", "StrongPass1!", role="admin"
                )
                admin_login = self.client.post(
                    "/api/auth/login",
                    json={"username": "jwt-admin", "password": "StrongPass1!"},
                )
                admin_token = admin_login.json()["access_token"]
                users = self.client.get(
                    "/api/admin/users",
                    headers={"Authorization": f"Bearer {admin_token}"},
                )
                self.assertEqual(users.status_code, 200)
                bob_id = bob.json()["user"]["id"]
                disabled = self.client.patch(
                    f"/api/admin/users/{bob_id}",
                    headers={"Authorization": f"Bearer {admin_token}"},
                    json={"is_active": False},
                )
                self.assertEqual(disabled.status_code, 200)
                self.assertFalse(disabled.json()["is_active"])
                self.assertEqual(
                    self.client.get(
                        "/api/conversations",
                        headers={"Authorization": f"Bearer {bob_token}"},
                    ).status_code,
                    401,
                )
        finally:
            app.dependency_overrides.pop(get_settings, None)

    def test_refresh_rotation_rejects_replay(self):
        settings = Settings(
            auth_enabled=True,
            jwt_secret="another-test-secret-longer-than-thirty-two-characters",
        )
        service = AuthService(self.database, settings)
        user = service.create_user("refresh-user", "StrongPass1!")
        access, refresh, _ = service.issue_token_pair(user)
        authenticated = service.authenticate_access_token(access)
        self.assertEqual(authenticated.id, user.id)

        _, rotated_access, rotated_refresh, _ = service.rotate_refresh_token(refresh)
        self.assertTrue(rotated_refresh)
        with self.assertRaises(Exception):
            service.rotate_refresh_token(refresh)
        with self.assertRaises(Exception):
            service.authenticate_access_token(rotated_access)

    def test_refresh_cookie_contract(self):
        settings = Settings(
            auth_enabled=True,
            auth_registration_enabled=False,
            jwt_secret="cookie-contract-secret-longer-than-thirty-two-characters",
            cookie_secure=False,
        )
        app.dependency_overrides[get_settings] = lambda: settings
        try:
            AuthService(self.database, settings).create_user("cookie-user", "StrongPass1!")
            with patch("backend.auth.get_settings", return_value=settings):
                login = self.client.post(
                    "/api/auth/login",
                    json={"username": "cookie-user", "password": "StrongPass1!"},
                )
                self.assertEqual(login.status_code, 200)
                self.assertNotIn("refresh_token", login.json())
                self.assertIn("HttpOnly", login.headers["set-cookie"])
                self.assertIn("Path=/api/auth", login.headers["set-cookie"])

                first_cookie = self.client.cookies.get("refresh_token")
                refreshed = self.client.post("/api/auth/refresh")
                self.assertEqual(refreshed.status_code, 200)
                self.assertNotIn("refresh_token", refreshed.json())
                self.assertNotEqual(first_cookie, self.client.cookies.get("refresh_token"))

                logged_out = self.client.post("/api/auth/logout")
                self.assertEqual(logged_out.status_code, 204)
                self.assertIn("Max-Age=0", logged_out.headers["set-cookie"])
        finally:
            app.dependency_overrides.pop(get_settings, None)


if __name__ == "__main__":
    unittest.main()
