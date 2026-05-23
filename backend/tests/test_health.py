def test_health_ok(client):
    r = client.get("/api/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert "version" in body


def test_ready_db_and_queue(client):
    r = client.get("/api/ready")
    assert r.status_code == 200
    body = r.json()
    assert body["ready"] is True
    assert body["checks"]["db"] is True
    assert body["checks"]["queue"] is True  # in-proc queue is always ready


def test_providers_public(client):
    r = client.get("/api/llm-providers")
    assert r.status_code == 200
    assert set(r.json().keys()) == {"gemini", "ollama"}
