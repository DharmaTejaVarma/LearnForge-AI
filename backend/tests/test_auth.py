import uuid
import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app

@pytest.mark.asyncio
async def test_user_registration_and_login():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        unique_email = f"student_{uuid.uuid4().hex[:8]}@learnforge.ai"
        reg_payload = {
            "email": unique_email,
            "password": "SecurePassword123!",
            "full_name": "Test Student"
        }
        # 1. Register new user
        reg_res = await client.post("/api/v1/auth/register", json=reg_payload)
        assert reg_res.status_code == 201
        reg_data = reg_res.json()
        assert "access_token" in reg_data
        assert reg_data["user"]["email"] == unique_email
        assert reg_data["user"]["full_name"] == "Test Student"
        assert "password" not in reg_data["user"]
        assert "hashed_password" not in reg_data["user"]

        token = reg_data["access_token"]

        # 2. Duplicate registration should return 409 Conflict
        dup_res = await client.post("/api/v1/auth/register", json=reg_payload)
        assert dup_res.status_code == 409
        dup_data = dup_res.json()
        assert dup_data["success"] is False
        assert dup_data["error"]["code"] == "ConflictException"

        # 3. Login with correct credentials
        login_res = await client.post("/api/v1/auth/login", json={
            "email": unique_email,
            "password": "SecurePassword123!"
        })
        assert login_res.status_code == 200
        login_data = login_res.json()
        assert "access_token" in login_data
        login_token = login_data["access_token"]

        # 4. Login with wrong password should return 401
        bad_login_res = await client.post("/api/v1/auth/login", json={
            "email": unique_email,
            "password": "WrongPassword!"
        })
        assert bad_login_res.status_code == 401

        # 5. Access protected /api/v1/users/me with token
        headers = {"Authorization": f"Bearer {login_token}"}
        me_res = await client.get("/api/v1/users/me", headers=headers)
        assert me_res.status_code == 200
        me_data = me_res.json()
        assert me_data["email"] == unique_email
        assert me_data["full_name"] == "Test Student"

        # 6. Access protected route with invalid token
        bad_token_res = await client.get("/api/v1/users/me", headers={"Authorization": "Bearer invalid.token.value"})
        assert bad_token_res.status_code == 401

        # 7. Access protected route without token
        no_token_res = await client.get("/api/v1/users/me")
        assert no_token_res.status_code == 401

        # 8. Update user profile
        update_res = await client.put("/api/v1/users/me", headers=headers, json={"full_name": "Updated Student Name"})
        assert update_res.status_code == 200
        assert update_res.json()["full_name"] == "Updated Student Name"

@pytest.mark.asyncio
async def test_user_data_isolation():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        email_a = f"alpha_{uuid.uuid4().hex[:8]}@learnforge.ai"
        email_b = f"beta_{uuid.uuid4().hex[:8]}@learnforge.ai"

        # Register User A
        res_a = await client.post("/api/v1/auth/register", json={
            "email": email_a,
            "password": "PasswordA123!",
            "full_name": "User Alpha"
        })
        token_a = res_a.json()["access_token"]

        # Register User B
        res_b = await client.post("/api/v1/auth/register", json={
            "email": email_b,
            "password": "PasswordB123!",
            "full_name": "User Beta"
        })
        token_b = res_b.json()["access_token"]

        # Request with Token A must return User A, never User B
        headers_a = {"Authorization": f"Bearer {token_a}"}
        me_a = await client.get("/api/v1/users/me", headers=headers_a)
        assert me_a.json()["email"] == email_a
        assert me_a.json()["full_name"] == "User Alpha"

        # Request with Token B must return User B
        headers_b = {"Authorization": f"Bearer {token_b}"}
        me_b = await client.get("/api/v1/users/me", headers=headers_b)
        assert me_b.json()["email"] == email_b
        assert me_b.json()["full_name"] == "User Beta"
