from __future__ import annotations


def test_health(client):
    assert client.get("/health").json()["status"] == "ok"
    assert client.get("/health/ready").json()["database"] == "ok"


def test_conditions_seeded(client):
    conditions = client.get("/v1/conditions").json()
    slugs = {c["slug"] for c in conditions}
    assert {"acne_vulgaris", "melanoma_suspected"} <= slugs
    mel = client.get("/v1/conditions/melanoma_suspected").json()
    assert mel["is_referral_trigger"] is True


def test_upload_requires_consent(client):
    client.post("/v1/auth/register", json={"email": "n@e.com", "password": "password123"})
    tok = client.post(
        "/v1/auth/login", json={"email": "n@e.com", "password": "password123"}
    ).json()["access_token"]
    r = client.post(
        "/v1/images",
        headers={"Authorization": f"Bearer {tok}"},
        files={"file": ("x.png", b"\x89PNG\r\n\x1a\n" + b"0" * 400, "image/png")},
    )
    assert r.status_code == 403


def test_full_flow(auth_client, png_bytes):
    up = auth_client.post(
        "/v1/images",
        files={"file": ("skin.png", png_bytes, "image/png")},
        data={"body_site": "forearm"},
    )
    assert up.status_code == 201, up.text
    image = up.json()
    assert image["status"] == "ready"
    assert image["width"] == 640

    an = auth_client.post(
        "/v1/analyses",
        json={"image_id": image["id"], "questionnaire": {"itch": True, "duration_days": 10}},
    )
    assert an.status_code == 201, an.text
    result = an.json()
    assert result["status"] in {"completed", "referred"}
    assert result["triage_level"] in {"routine", "soon", "urgent"}
    assert len(result["predictions"]) >= 1
    assert result["predictions"][0]["rank"] == 1
    assert "not a medical diagnosis" in result["disclaimer"].lower()

    # deterministic: same bytes -> same top raw label
    an2 = auth_client.post("/v1/analyses", json={"image_id": image["id"]})
    assert (
        an2.json()["predictions"][0]["raw_label"]
        == result["predictions"][0]["raw_label"]
    )

    fb = auth_client.post(
        f"/v1/analyses/{result['id']}/feedback",
        json={"helpfulness_rating": 4, "was_accurate": True},
    )
    assert fb.status_code == 201

    listing = auth_client.get("/v1/analyses").json()
    assert len(listing) == 2


def test_referral_path_for_malignancy_symptoms(auth_client, png_bytes):
    image = auth_client.post(
        "/v1/images", files={"file": ("s.png", png_bytes, "image/png")}
    ).json()
    result = auth_client.post(
        "/v1/analyses",
        json={
            "image_id": image["id"],
            "questionnaire": {"recent_change": True, "bleeding": True},
        },
    ).json()
    assert result["triage_level"] == "urgent"
    assert result["status"] == "referred"
    assert any(f["level"] == "urgent" for f in result["flags"])


def test_image_delete_purges_bytes(auth_client, png_bytes):
    image = auth_client.post(
        "/v1/images", files={"file": ("s.png", png_bytes, "image/png")}
    ).json()
    url = auth_client.get(f"/v1/images/{image['id']}/download-url").json()["url"]
    assert auth_client.get(url).status_code == 200
    assert auth_client.delete(f"/v1/images/{image['id']}").status_code == 204
    assert auth_client.get(f"/v1/images/{image['id']}").status_code == 404
