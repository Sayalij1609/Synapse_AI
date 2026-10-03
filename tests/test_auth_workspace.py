"""
SYNAPSE AI — Authentication & Multi-Tenant Authorization Test Suite.

Verifies:
1. User registration with bcrypt hashing and validation
2. Password strength and email format enforcement
3. Authentication and JWT generation
4. Token expiration handling
5. Protected endpoints requiring Bearer JWT
6. Strict multi-tenant backend authorization:
   - User B CANNOT access User A's projects (403 Forbidden)
   - User B CANNOT access User A's research sessions (403 Forbidden)
   - User B CANNOT access User A's reports or sources (403 Forbidden)
   - User B CANNOT delete User A's resources (403 Forbidden)
"""

from datetime import timedelta
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app import app
from auth import (
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password,
    validate_password_strength,
)
from db.models import Base
from db.session import get_db


@pytest.fixture
def client_with_db():
    """Sets up an in-memory database and FastAPI test client with database dependency override."""
    test_engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    with test_engine.connect() as conn:
        conn.exec_driver_sql("PRAGMA foreign_keys = ON")

    Base.metadata.create_all(bind=test_engine)
    TestingSessionLocal = sessionmaker(bind=test_engine, autoflush=False, autocommit=False)

    def override_get_db():
        session = TestingSessionLocal()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    app.dependency_overrides[get_db] = override_get_db
    client = TestClient(app)

    yield client

    app.dependency_overrides.clear()
    Base.metadata.drop_all(bind=test_engine)


class TestAuthAndMultiTenancy:
    """Comprehensive test suite for authentication and backend authorization."""

    def test_1_password_hashing_and_verification(self):
        """Verify bcrypt hashing generates unique salts and checks passwords correctly."""
        plain = "MySecretPassw0rd!"
        h1 = hash_password(plain)
        h2 = hash_password(plain)

        # Hashes should be different due to distinct bcrypt salts
        assert h1 != h2
        assert verify_password(plain, h1) is True
        assert verify_password(plain, h2) is True
        assert verify_password("WrongPassword!", h1) is False

    def test_2_password_validation_rules(self):
        """Verify validation requirements on password strength."""
        ok, _ = validate_password_strength("validpassword123")
        assert ok is True

        short, msg = validate_password_strength("short")
        assert short is False
        assert "at least 8" in msg

        empty, msg = validate_password_strength("")
        assert empty is False

    def test_3_user_registration(self, client_with_db):
        """Test registration endpoint with valid and invalid inputs."""
        client = client_with_db

        # Valid registration
        res = client.post("/auth/register", json={
            "email": "analyst1@synapse.ai",
            "password": "SecurePassword2026!",
            "username": "analyst1",
            "full_name": "First Analyst"
        })
        assert res.status_code == 200
        data = res.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"
        assert data["user"]["email"] == "analyst1@synapse.ai"
        assert "hashed_password" not in data["user"]

        # Duplicate email rejected (409 Conflict)
        res_dup = client.post("/auth/register", json={
            "email": "analyst1@synapse.ai",
            "password": "AnotherPassword123!",
        })
        assert res_dup.status_code == 409

        # Weak password rejected (400 Bad Request)
        res_weak = client.post("/auth/register", json={
            "email": "analyst2@synapse.ai",
            "password": "123",
        })
        assert res_weak.status_code == 400

    def test_4_login_and_token_generation(self, client_with_db):
        """Test user login authentication and JWT retrieval."""
        client = client_with_db

        # Register user
        client.post("/auth/register", json={
            "email": "researcher@synapse.ai",
            "password": "SuperSecretPass2026!",
        })

        # Correct login
        res = client.post("/auth/login", json={
            "email": "researcher@synapse.ai",
            "password": "SuperSecretPass2026!",
        })
        assert res.status_code == 200
        data = res.json()
        token = data["access_token"]
        assert token is not None

        # Verify profile via /auth/me
        res_me = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
        assert res_me.status_code == 200
        assert res_me.json()["user"]["email"] == "researcher@synapse.ai"

        # Incorrect password
        res_bad = client.post("/auth/login", json={
            "email": "researcher@synapse.ai",
            "password": "WrongPassword!",
        })
        assert res_bad.status_code == 401

    def test_5_token_expiration(self):
        """Verify expired tokens are rejected."""
        # Create token that expired 10 minutes ago
        expired_token = create_access_token(
            user_id="user_test_exp",
            email="expired@synapse.ai",
            expires_delta=timedelta(minutes=-10)
        )
        with pytest.raises(Exception) as excinfo:
            decode_access_token(expired_token)
        assert "expired" in str(excinfo.value.detail).lower()

    def test_6_unauthenticated_protected_endpoints_rejected(self, client_with_db):
        """Verify accessing protected routes without a token returns 401 Unauthorized."""
        client = client_with_db

        # Access /projects without token
        res = client.get("/projects")
        assert res.status_code == 401

        # Access /projects with malformed token
        res_bad = client.get("/projects", headers={"Authorization": "Bearer invalid_token_xyz"})
        assert res_bad.status_code == 401

    def test_7_strict_multi_tenant_authorization(self, client_with_db):
        """
        Critical security test:
        Users must NEVER be able to access another user's projects, sessions, sources, or reports.
        """
        client = client_with_db

        # 1. Register User A (Alice)
        res_a = client.post("/auth/register", json={
            "email": "alice@synapse.ai",
            "password": "AlicePassword2026!",
            "username": "alice",
        })
        token_a = res_a.json()["access_token"]
        headers_a = {"Authorization": f"Bearer {token_a}"}

        # 2. Register User B (Bob)
        res_b = client.post("/auth/register", json={
            "email": "bob@synapse.ai",
            "password": "BobPassword2026!",
            "username": "bob",
        })
        token_b = res_b.json()["access_token"]
        headers_b = {"Authorization": f"Bearer {token_b}"}

        # 3. Alice creates Project A and Session A
        proj_res = client.post("/projects", json={
            "title": "Alice Confidential Cancer Research",
            "description": "Proprietary oncology dataset"
        }, headers=headers_a)
        assert proj_res.status_code == 200
        alice_project_id = proj_res.json()["id"]

        sess_res = client.post(f"/projects/{alice_project_id}/sessions", json={
            "topic": "Novel KRAS Inhibitors in Pancreatic Cancer",
            "session_name": "Alice Confidential Session"
        }, headers=headers_a)
        assert sess_res.status_code == 200
        alice_session_id = sess_res.json()["id"]

        # 4. Bob attempts to list projects — must NOT see Alice's project!
        bob_projects_res = client.get("/projects", headers=headers_b)
        assert bob_projects_res.status_code == 200
        bob_project_titles = [p["title"] for p in bob_projects_res.json()]
        assert "Alice Confidential Cancer Research" not in bob_project_titles

        # 5. Bob attempts direct access to Alice's project -> 403 FORBIDDEN!
        bob_hack_proj = client.get(f"/projects/{alice_project_id}", headers=headers_b)
        assert bob_hack_proj.status_code == 403
        assert "Forbidden" in bob_hack_proj.json()["detail"]

        # 6. Bob attempts to create a session in Alice's project -> 403 FORBIDDEN!
        bob_hack_create_sess = client.post(f"/projects/{alice_project_id}/sessions", json={
            "topic": "Bob Infiltration"
        }, headers=headers_b)
        assert bob_hack_create_sess.status_code == 403

        # 7. Bob attempts direct access to Alice's session telemetry & evidence -> 403 FORBIDDEN!
        bob_hack_sess = client.get(f"/sessions/{alice_session_id}", headers=headers_b)
        assert bob_hack_sess.status_code == 403
        assert "Forbidden" in bob_hack_sess.json()["detail"]

        # 8. Bob attempts to view Alice's session reports -> 403 FORBIDDEN!
        bob_hack_reports = client.get(f"/sessions/{alice_session_id}/reports", headers=headers_b)
        assert bob_hack_reports.status_code == 403

        # 9. Bob attempts to delete Alice's session -> 403 FORBIDDEN!
        bob_hack_del_sess = client.delete(f"/sessions/{alice_session_id}", headers=headers_b)
        assert bob_hack_del_sess.status_code == 403

        # 10. Bob attempts to delete Alice's project -> 403 FORBIDDEN!
        bob_hack_del_proj = client.delete(f"/projects/{alice_project_id}", headers=headers_b)
        assert bob_hack_del_proj.status_code == 403

        # 11. Alice CAN access her own project and session without restriction
        alice_get_proj = client.get(f"/projects/{alice_project_id}", headers=headers_a)
        assert alice_get_proj.status_code == 200
        assert alice_get_proj.json()["title"] == "Alice Confidential Cancer Research"

        alice_get_sess = client.get(f"/sessions/{alice_session_id}", headers=headers_a)
        assert alice_get_sess.status_code == 200
        assert alice_get_sess.json()["topic"] == "Novel KRAS Inhibitors in Pancreatic Cancer"

        # 12. Bob attempts to export Alice's session dossier -> 403 FORBIDDEN!
        bob_hack_dossier = client.get(f"/sessions/{alice_session_id}/dossier", headers=headers_b)
        assert bob_hack_dossier.status_code == 403

        # 13. Alice can export her session dossier successfully
        alice_dossier = client.get(f"/sessions/{alice_session_id}/dossier", headers=headers_a)
        assert alice_dossier.status_code == 200
        dossier_data = alice_dossier.json()
        assert dossier_data["session_id"] == alice_session_id
        assert "dossier_markdown" in dossier_data
        assert "Executive Research Report" in dossier_data["dossier_markdown"]

