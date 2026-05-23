def test_register_login_me(client):
    r = client.post(
        "/api/auth/register",
        json={"email": "a@b.com", "password": "supersecret123"},
    )
    assert r.status_code == 200
    token = r.json()["access_token"]
    assert token

    r = client.post(
        "/api/auth/login",
        json={"email": "a@b.com", "password": "supersecret123"},
    )
    assert r.status_code == 200
    token2 = r.json()["access_token"]
    assert token2

    r = client.get(
        "/api/auth/me", headers={"Authorization": f"Bearer {token2}"}
    )
    assert r.status_code == 200
    assert r.json()["email"] == "a@b.com"


def test_register_rejects_duplicate(client):
    payload = {"email": "dup@b.com", "password": "supersecret123"}
    assert client.post("/api/auth/register", json=payload).status_code == 200
    r = client.post("/api/auth/register", json=payload)
    assert r.status_code == 400


def test_login_wrong_password(client):
    client.post(
        "/api/auth/register",
        json={"email": "x@b.com", "password": "supersecret123"},
    )
    r = client.post(
        "/api/auth/login",
        json={"email": "x@b.com", "password": "wrong-password"},
    )
    assert r.status_code == 401


def test_me_requires_token(client):
    r = client.get("/api/auth/me")
    assert r.status_code == 401


def test_me_rejects_bad_token(client):
    r = client.get(
        "/api/auth/me", headers={"Authorization": "Bearer not.a.real.token"}
    )
    assert r.status_code == 401


def test_register_validates_password_length(client):
    r = client.post(
        "/api/auth/register", json={"email": "a@b.com", "password": "short"}
    )
    assert r.status_code == 422
