"""Focused regression tests for backend fixes.

Run from repo root:
    .venv/bin/python -m unittest backend.tests.test_backend_regressions -v

Uses the app with its SQLite fallback database, so it needs no external
PostgreSQL or valid LLM keys. Placeholder keys must behave as "no key".
"""
import unittest
import uuid

from fastapi.testclient import TestClient

from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool
from sqlalchemy.orm import sessionmaker
from backend.app.core.database import Base, get_db
from backend.app.main import app
from backend.app.routers.personas import seed_default_personas
from backend.app.memory.manager import memory_manager

test_engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
TestingSession = sessionmaker(bind=test_engine)
import backend.app.routers.messages as message_routes
message_routes.SessionLocal = TestingSession
def test_db():
    with TestingSession() as db:
        yield db
app.dependency_overrides[get_db] = test_db
Base.metadata.create_all(test_engine)
with TestingSession() as db:
    seed_default_personas(db)


def register_user(client: TestClient, label: str = "user") -> dict:
    email = f"{label}-{uuid.uuid4().hex[:12]}@example.com"
    r = client.post(
        "/api/auth/register",
        json={"username": f"Test {label}", "email": email, "password": "test-password-123"},
    )
    assert r.status_code == 201, r.text
    body = r.json()
    return {"headers": {"Authorization": f"Bearer {body['access_token']}"}, "email": email, "user": body["user"]}


class BackendRegressionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)

    def setUp(self):
        self.client.cookies.clear()
        self.auth = register_user(self.client)

    def test_persona_default_memory_is_used_when_omitted(self):
        r = self.client.post(
            "/api/conversations",
            json={"title": "regression-persona-default", "persona_id": "code_helper"},
            headers=self.auth["headers"],
        )
        self.assertEqual(r.status_code, 201, r.text)
        self.assertEqual(r.json()["memory_type"], "entity")

    def test_hybrid_is_a_real_strategy_not_buffer_fallback(self):
        strategy = memory_manager.get_memory_strategy("hybrid")
        self.assertEqual(strategy.memory_type, "hybrid")

    def test_message_with_placeholder_keys_uses_mock_not_api_error(self):
        r = self.client.post(
            "/api/conversations",
            json={
                "title": "regression-mock-stream",
                "persona_id": "general_assistant",
                "memory_type": "buffer",
            },
            headers=self.auth["headers"],
        )
        self.assertEqual(r.status_code, 201, r.text)
        cid = r.json()["id"]
        with self.client.stream(
            "POST", f"/api/conversations/{cid}/messages", json={"content": "Hello there"}, headers=self.auth["headers"]
        ) as resp:
            self.assertEqual(resp.status_code, 200)
            body = "".join(resp.iter_text())
        self.assertNotIn("[API Error", body)
        self.assertIn("development", body)
        msgs = self.client.get(f"/api/conversations/{cid}/messages", headers=self.auth["headers"])
        self.assertEqual(msgs.status_code, 200)
        assistant = [m for m in msgs.json() if m["role"] == "assistant"]
        self.assertTrue(assistant)
        self.assertNotIn("[API Error", assistant[-1]["content"])
        self.assertIn("preview mode", assistant[-1]["content"])

    def test_global_entity_can_be_deleted(self):
        r = self.client.post(
            "/api/conversations",
            json={
                "title": "regression-global-delete",
                "persona_id": "general_assistant",
                "memory_type": "entity",
            },
            headers=self.auth["headers"],
        )
        self.assertEqual(r.status_code, 201, r.text)
        cid = r.json()["id"]
        created = self.client.post(
            f"/api/conversations/{cid}/memory/entities",
            json={
                "name": "Regression Global Fact",
                "entity_type": "concept",
                "description": "shared across sessions",
                "is_global": True,
            },
            headers=self.auth["headers"],
        )
        self.assertEqual(created.status_code, 201, created.text)
        eid = created.json()["id"]
        deleted = self.client.delete(f"/api/conversations/{cid}/memory/entities/{eid}", headers=self.auth["headers"])
        self.assertEqual(deleted.status_code, 200, deleted.text)

    def test_accounts_only_see_their_own_conversations(self):
        owner = self.auth
        other = register_user(self.client, "other")
        created = self.client.post(
            "/api/conversations",
            json={"title": "owner-only-chat", "persona_id": "general_assistant", "memory_type": "buffer"},
            headers=owner["headers"],
        )
        self.assertEqual(created.status_code, 201, created.text)
        cid = created.json()["id"]
        # Owner sees it; the other account does not.
        own_list = self.client.get("/api/conversations", headers=owner["headers"])
        self.assertIn(cid, [c["id"] for c in own_list.json()])
        other_list = self.client.get("/api/conversations", headers=other["headers"])
        self.assertNotIn(cid, [c["id"] for c in other_list.json()])
        # Direct access from another account reads as not found.
        for method, path in [
            ("GET", f"/api/conversations/{cid}"),
            ("GET", f"/api/conversations/{cid}/messages"),
            ("GET", f"/api/conversations/{cid}/memory/entities"),
            ("GET", f"/api/conversations/{cid}/export"),
            ("GET", f"/api/conversations/{cid}/memory/summary"),
            ("GET", f"/api/conversations/{cid}/memory/graph"),
            ("GET", f"/api/conversations/{cid}/memory/tokens"),
            ("DELETE", f"/api/conversations/{cid}/messages"),
        ]:
            resp = self.client.request(method, path, headers=other["headers"])
            self.assertEqual(resp.status_code, 404, f"{method} {path}: {resp.text}")
        denied_send = self.client.post(f"/api/conversations/{cid}/messages", json={"content": "hijacked"}, headers=other["headers"])
        self.assertEqual(denied_send.status_code, 404, denied_send.text)
        patch = self.client.patch(
            f"/api/conversations/{cid}", json={"title": "hijacked"}, headers=other["headers"]
        )
        self.assertEqual(patch.status_code, 404, patch.text)
        delete = self.client.delete(f"/api/conversations/{cid}", headers=other["headers"])
        self.assertEqual(delete.status_code, 404, delete.text)
        # Signed-out requests are rejected.
        self.client.cookies.clear()
        anon = self.client.get("/api/conversations")
        self.assertEqual(anon.status_code, 401, anon.text)
        # Global facts stay with their owner across that owner's chats only.
        mine = self.client.post(
            f"/api/conversations/{cid}/memory/entities",
            json={"name": "Owner Secret Project", "entity_type": "project", "description": "private", "is_global": True},
            headers=owner["headers"],
        )
        self.assertEqual(mine.status_code, 201, mine.text)
        other_conv = self.client.post(
            "/api/conversations",
            json={"title": "other-chat", "persona_id": "general_assistant", "memory_type": "entity"},
            headers=other["headers"],
        ).json()["id"]
        seen = self.client.get(f"/api/conversations/{other_conv}/memory/entities", headers=other["headers"])
        self.assertNotIn("Owner Secret Project", [e["name"] for e in seen.json()])

    def test_private_cookie_session_logout_and_csrf(self):
        result = self.client.post('/api/auth/login', json={'email': self.auth['email'], 'password': 'test-password-123'})
        self.assertIn('HttpOnly', result.headers['set-cookie'])
        self.assertIn('SameSite=strict', result.headers['set-cookie'])
        self.assertEqual(self.client.get('/api/auth/me').status_code, 200)
        self.assertEqual(self.client.get('/api/auth/me').headers['cache-control'], 'no-store')
        self.assertEqual(self.client.post('/api/auth/logout', headers={'Origin': 'https://attacker.example'}).status_code, 403)
        self.client.post('/api/auth/logout')
        self.assertEqual(self.client.get('/api/auth/me').status_code, 401)
        self.assertEqual(self.client.get('/api/auth/me', headers={'Authorization': 'Bearer invalid.token.value'}).status_code, 401)

    def test_number_maps_to_owner_and_private_personas(self):
        owner = register_user(self.client, 'persona-owner')
        created = self.client.post('/api/personas', headers=owner['headers'], json={
            'id': uuid.uuid4().hex, 'name': 'Private persona', 'system_prompt': 'Private instructions'
        })
        self.assertEqual(created.status_code, 201, created.text)
        pid = created.json()['id']
        for method, path, data in [
            ('GET', '/api/personas/'+pid, None),
            ('DELETE', '/api/personas/'+pid, None),
            ('POST', '/api/conversations', {'persona_id': pid}),
        ]:
            result = self.client.request(method, path, json=data, headers=self.auth['headers'])
            self.assertEqual(result.status_code, 404, result.text)
        other_list = self.client.get('/api/personas', headers=self.auth['headers']).json()
        self.assertNotIn(pid, [p['id'] for p in other_list])
        email = uuid.uuid4().hex+'@example.com'
        result = self.client.post('/api/auth/register', json={'username': 'Numeric', 'email': email, 'password': 'test-password-123', 'profile_number': '123'})
        self.assertEqual(result.status_code, 201, result.text)
        self.assertEqual(result.json()['user']['profile_number'], '123')
        self.assertEqual(self.client.get('/api/auth/me').json()['profile_number'], '123')
        self.assertNotIn('password_hash', result.json()['user'])

    def test_login_rejects_wrong_password_and_duplicate_email(self):
        email = self.auth["email"]
        wrong = self.client.post("/api/auth/login", json={"email": email, "password": "wrong-password"})
        self.assertEqual(wrong.status_code, 401, wrong.text)
        ok = self.client.post("/api/auth/login", json={"email": email, "password": "test-password-123"})
        self.assertEqual(ok.status_code, 200, ok.text)
        dup = self.client.post(
            "/api/auth/register",
            json={"username": "Copy", "email": email, "password": "test-password-123"},
        )
        self.assertEqual(dup.status_code, 409, dup.text)
        me = self.client.get("/api/auth/me", headers=self.auth["headers"])
        self.assertEqual(me.status_code, 200, me.text)
        self.assertEqual(me.json()["email"], email)


if __name__ == "__main__":
    unittest.main()
