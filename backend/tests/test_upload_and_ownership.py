import uuid


def _upload(client, headers, pdf_bytes):
    return client.post(
        "/api/upload",
        headers=headers,
        files={"file": ("sample.pdf", pdf_bytes, "application/pdf")},
        data={"subject": "Mathematics", "provider": "gemini"},
    )


def test_upload_requires_auth(client, sample_pdf_bytes):
    r = client.post(
        "/api/upload",
        files={"file": ("a.pdf", sample_pdf_bytes, "application/pdf")},
        data={"subject": "Mathematics", "provider": "gemini"},
    )
    assert r.status_code == 401


def test_upload_rejects_non_pdf(client, auth_headers):
    r = client.post(
        "/api/upload",
        headers=auth_headers,
        files={"file": ("a.txt", b"hello", "text/plain")},
        data={"subject": "Mathematics", "provider": "gemini"},
    )
    assert r.status_code == 400


def test_upload_rejects_bad_magic(client, auth_headers):
    r = client.post(
        "/api/upload",
        headers=auth_headers,
        files={"file": ("a.pdf", b"NOT-A-PDF", "application/pdf")},
        data={"subject": "Mathematics", "provider": "gemini"},
    )
    assert r.status_code == 400


def test_upload_rejects_unknown_provider(client, auth_headers, sample_pdf_bytes):
    r = client.post(
        "/api/upload",
        headers=auth_headers,
        files={"file": ("a.pdf", sample_pdf_bytes, "application/pdf")},
        data={"subject": "Mathematics", "provider": "bogus"},
    )
    assert r.status_code == 400


def test_upload_ok_and_extracts(client, auth_headers, sample_pdf_bytes):
    r = _upload(client, auth_headers, sample_pdf_bytes)
    assert r.status_code == 200, r.text
    job_id = r.json()["id"]
    r2 = client.get(f"/api/jobs/{job_id}", headers=auth_headers)
    assert r2.status_code == 200
    assert r2.json()["status"] == "done"
    assert r2.json()["question_count"] == 1

    r3 = client.get(f"/api/jobs/{job_id}/questions", headers=auth_headers)
    assert r3.status_code == 200
    qs = r3.json()
    assert len(qs) == 1
    assert qs[0]["correct_answer"] == "B"


def test_multiple_uploads_allowed_by_default(
    client, auth_headers, sample_pdf_bytes
):
    assert _upload(client, auth_headers, sample_pdf_bytes).status_code == 200
    assert _upload(client, auth_headers, sample_pdf_bytes).status_code == 200


def test_me_reports_upload_count(client, auth_headers, sample_pdf_bytes):
    r = client.get("/api/auth/me", headers=auth_headers)
    assert r.status_code == 200
    assert r.json()["upload_count"] == 0

    _upload(client, auth_headers, sample_pdf_bytes)
    r2 = client.get("/api/auth/me", headers=auth_headers)
    assert r2.json()["upload_count"] == 1


def test_other_user_cannot_see_job(client, auth_headers, sample_pdf_bytes):
    r = _upload(client, auth_headers, sample_pdf_bytes)
    job_id = r.json()["id"]

    email = f"other-{uuid.uuid4().hex[:8]}@example.com"
    r2 = client.post(
        "/api/auth/register",
        json={"email": email, "password": "supersecret123"},
    )
    other_headers = {"Authorization": f"Bearer {r2.json()['access_token']}"}

    assert client.get(f"/api/jobs/{job_id}", headers=other_headers).status_code == 404
    assert (
        client.get(f"/api/jobs/{job_id}/questions", headers=other_headers).status_code
        == 404
    )


def test_other_user_cannot_edit_question(client, auth_headers, sample_pdf_bytes):
    r = _upload(client, auth_headers, sample_pdf_bytes)
    job_id = r.json()["id"]
    qs = client.get(f"/api/jobs/{job_id}/questions", headers=auth_headers).json()
    qid = qs[0]["id"]

    email = f"other-{uuid.uuid4().hex[:8]}@example.com"
    r2 = client.post(
        "/api/auth/register",
        json={"email": email, "password": "supersecret123"},
    )
    other_headers = {"Authorization": f"Bearer {r2.json()['access_token']}"}

    r3 = client.put(
        f"/api/questions/{qid}",
        headers=other_headers,
        json={"question_text": "Hacked"},
    )
    assert r3.status_code == 404


def test_list_jobs_only_shows_own_jobs(client, auth_headers, sample_pdf_bytes):
    r = _upload(client, auth_headers, sample_pdf_bytes)
    job_id = r.json()["id"]

    email = f"other-{uuid.uuid4().hex[:8]}@example.com"
    r2 = client.post(
        "/api/auth/register",
        json={"email": email, "password": "supersecret123"},
    )
    other_headers = {"Authorization": f"Bearer {r2.json()['access_token']}"}

    owner_jobs = client.get("/api/jobs", headers=auth_headers).json()
    other_jobs = client.get("/api/jobs", headers=other_headers).json()

    assert any(j["id"] == job_id for j in owner_jobs)
    assert not any(j["id"] == job_id for j in other_jobs)


def test_owner_can_edit_question_and_html_is_stripped(
    client, auth_headers, sample_pdf_bytes
):
    r = _upload(client, auth_headers, sample_pdf_bytes)
    job_id = r.json()["id"]
    qid = client.get(f"/api/jobs/{job_id}/questions", headers=auth_headers).json()[0][
        "id"
    ]

    r2 = client.put(
        f"/api/questions/{qid}",
        headers=auth_headers,
        json={
            "question_text": "Safe <script>alert(1)</script> text",
            "option_a": "<b>plain</b>",
        },
    )
    assert r2.status_code == 200
    body = r2.json()
    assert "<script>" not in body["question_text"]
    assert "<b>" not in body["option_a"]
