# Skin Diagnosis API — Step-by-Step Guide

A complete, ordered walkthrough of the API: register → consent → upload a photo
→ run an analysis → read the result → give feedback. For *why* each endpoint
and table exists, see [DESIGN.md](DESIGN.md); this doc is the *how*.

Base URL (local dev): `http://127.0.0.1:8000`
Interactive docs: `http://127.0.0.1:8000/docs`

Every step below is a real `curl` call against the running app
(`uvicorn app.main:app --reload`). Swap in your own values where noted.

---

## Step 0 — Health check (no auth)

```bash
curl -s localhost:8000/health
```
```json
{"status": "ok", "app": "skin-diagnosis-app", "environment": "development"}
```

---

## Step 1 — Register an account

`POST /v1/auth/register`

```bash
curl -s localhost:8000/v1/auth/register \
  -H 'content-type: application/json' \
  -d '{
        "email": "patient@example.com",
        "password": "supersecret1",
        "full_name": "Jane Doe"
      }'
```

**201 Created**
```json
{
  "id": "b9c1...uuid",
  "email": "patient@example.com",
  "full_name": "Jane Doe",
  "role": "patient",
  "is_active": true,
  "date_of_birth": null,
  "skin_type": null,
  "created_at": "2026-09-14T10:00:00Z"
}
```
`409 Conflict` if the email is already registered. Password must be 8–128 chars.

---

## Step 2 — Log in to get a JWT

`POST /v1/auth/login`

```bash
curl -s localhost:8000/v1/auth/login \
  -H 'content-type: application/json' \
  -d '{"email": "patient@example.com", "password": "supersecret1"}'
```

**200 OK**
```json
{"access_token": "eyJhbGciOi...", "token_type": "bearer", "expires_in": 86400}
```

Save the token — every step below sends it as `Authorization: Bearer <token>`.

```bash
export TOKEN="eyJhbGciOi..."
```

`401 Unauthorized` on wrong credentials.

---

## Step 3 — Confirm identity (optional sanity check)

`GET /v1/auth/me`

```bash
curl -s localhost:8000/v1/auth/me -H "Authorization: Bearer $TOKEN"
```
Returns the same shape as Step 1.

---

## Step 4 — Grant consent (required before any upload)

`POST /v1/consents` — the image upload endpoint checks these and returns `403`
if either is missing. Do this once per account.

```bash
curl -s localhost:8000/v1/consents -H "Authorization: Bearer $TOKEN" \
  -H 'content-type: application/json' \
  -d '{"consent_type": "image_storage", "granted": true}'

curl -s localhost:8000/v1/consents -H "Authorization: Bearer $TOKEN" \
  -H 'content-type: application/json' \
  -d '{"consent_type": "ai_processing", "granted": true}'
```

**200 OK** (each call)
```json
{
  "id": "c1a2...uuid",
  "consent_type": "image_storage",
  "granted": true,
  "granted_at": "2026-09-14T10:01:00Z",
  "revoked_at": null,
  "policy_version": "1.0"
}
```

Valid `consent_type` values: `image_storage`, `ai_processing`, `research_use`,
`share_with_clinician`.

Check what's on file any time:
```bash
curl -s localhost:8000/v1/consents -H "Authorization: Bearer $TOKEN"
```

---

## Step 5 — Upload a skin photo

`POST /v1/images` — `multipart/form-data`. Runs the quality gate (type, size,
dimensions, exposure/contrast) synchronously and stores the bytes.

```bash
curl -s localhost:8000/v1/images -H "Authorization: Bearer $TOKEN" \
  -F "file=@/path/to/skin.jpg" \
  -F "body_site=forearm" \
  -F "captured_at=2026-09-14T09:30:00Z"
```

**201 Created**
```json
{
  "id": "img_...uuid",
  "content_type": "image/jpeg",
  "byte_size": 482113,
  "width": 1024,
  "height": 768,
  "body_site": "forearm",
  "status": "ready",
  "quality_report": {
    "checks": {"magic_matches_declared": true, "min_dimension": true},
    "sniffed_content_type": "image/jpeg",
    "width": 1024, "height": 768,
    "exposure_mean": 132.4, "contrast_stddev": 41.2,
    "warnings": [], "passed": true
  },
  "captured_at": "2026-09-14T09:30:00Z",
  "created_at": "2026-09-14T10:02:00Z"
}
```

Save `id` — you'll pass it as `image_id` next.

```bash
export IMAGE_ID="img_...uuid"
```

Failure modes:
- `403` — missing `image_storage` or `ai_processing` consent (go back to Step 4)
- `413` — file larger than `SKINDX_MAX_UPLOAD_BYTES` (default 8 MB)
- `422` — empty file
- `201` with `"status": "quality_failed"` — file uploaded but unusable (wrong
  type, unreadable, too small); `quality_report.reason` explains why. **An
  analysis cannot be run against this image** — retake the photo and re-upload.

You can list or inspect images later:
```bash
curl -s localhost:8000/v1/images -H "Authorization: Bearer $TOKEN"
curl -s localhost:8000/v1/images/$IMAGE_ID -H "Authorization: Bearer $TOKEN"
```

---

## Step 6 — Run the analysis

`POST /v1/analyses` — the core endpoint. Body is `image_id` plus an optional
symptom questionnaire that feeds the safety-triage rules.

```bash
curl -s localhost:8000/v1/analyses -H "Authorization: Bearer $TOKEN" \
  -H 'content-type: application/json' \
  -d '{
        "image_id": "'"$IMAGE_ID"'",
        "questionnaire": {
          "itch": true,
          "duration_days": 14,
          "pain": false,
          "spreading": false,
          "bleeding": false,
          "recent_change": false,
          "prior_similar": true
        }
      }'
```

All questionnaire fields are optional — omit `questionnaire` entirely for an
image-only assessment.

**201 Created**
```json
{
  "id": "an_...uuid",
  "image_id": "img_...uuid",
  "status": "completed",
  "triage_level": "routine",
  "model_version": "mock-v0.1.0",
  "created_at": "2026-09-14T10:03:00Z",
  "inference_adapter": "mock",
  "questionnaire": {"itch": true, "duration_days": 14, "prior_similar": true},
  "triage_rationale": "Best match: Eczema (atopic dermatitis) (38% confidence). See a clinician for widespread, infected...",
  "disclaimer_version": "1.0",
  "disclaimer": "This assessment is generated by software for educational and informational purposes only. It is not a medical diagnosis...",
  "error_detail": null,
  "latency_ms": 4,
  "predictions": [
    {
      "raw_label": "atopic_dermatitis",
      "confidence": 0.38,
      "rank": 1,
      "is_primary": true,
      "mapped_ok": true,
      "condition": {
        "id": "cond_...uuid",
        "slug": "atopic_dermatitis",
        "display_name": "Eczema (atopic dermatitis)",
        "category": "inflammatory",
        "summary": "A chronic, itchy, relapsing inflammation...",
        "common_symptoms": ["intense itch", "dry rough skin", "..."],
        "typical_body_sites": ["inner elbows", "behind knees", "..."],
        "self_care_guidance": "Frequent fragrance-free emollients...",
        "when_to_see_doctor": "See a clinician for widespread, infected...",
        "reference_url": "https://www.aad.org/public/diseases",
        "default_triage_level": "routine",
        "is_referral_trigger": false
      }
    },
    { "raw_label": "contact_dermatitis", "confidence": 0.24, "rank": 2, "...": "..." }
  ],
  "flags": []
}
```

`status` is `completed` normally, or **`referred`** when `triage_level` comes
out `urgent` (e.g. a malignancy-pattern prediction, or `recent_change`/`bleeding`
answered `true` in the questionnaire) — `flags` then explains why.

Failure modes:
- `404` — `image_id` doesn't exist or isn't yours
- `422` — the image's `status` is `quality_failed`

Save the analysis id:
```bash
export ANALYSIS_ID="an_...uuid"
```

---

## Step 7 — Read the result again later

`GET /v1/analyses/{id}` — identical shape to the Step 6 response.

```bash
curl -s localhost:8000/v1/analyses/$ANALYSIS_ID -H "Authorization: Bearer $TOKEN"
```

---

## Step 8 — List analysis history

`GET /v1/analyses` — lightweight summaries, newest first.

```bash
curl -s localhost:8000/v1/analyses -H "Authorization: Bearer $TOKEN"
```
```json
[
  {
    "id": "an_...uuid", "image_id": "img_...uuid", "status": "completed",
    "triage_level": "routine", "model_version": "mock-v0.1.0",
    "created_at": "2026-09-14T10:03:00Z"
  }
]
```

---

## Step 9 — Submit feedback on a result

`POST /v1/analyses/{id}/feedback` — patients rate their own results; a
`clinician`-role account may also submit a correction on anyone's analysis.
At least one field is required.

```bash
curl -s localhost:8000/v1/analyses/$ANALYSIS_ID/feedback \
  -H "Authorization: Bearer $TOKEN" -H 'content-type: application/json' \
  -d '{"helpfulness_rating": 4, "was_accurate": true}'
```

**201 Created**
```json
{
  "id": "fb_...uuid",
  "analysis_id": "an_...uuid",
  "submitter_role": "patient",
  "helpfulness_rating": 4,
  "was_accurate": true,
  "corrected_condition_id": null,
  "comment": null,
  "created_at": "2026-09-14T10:05:00Z"
}
```

A clinician correcting a diagnosis instead:
```bash
curl -s localhost:8000/v1/analyses/$ANALYSIS_ID/feedback \
  -H "Authorization: Bearer $CLINICIAN_TOKEN" -H 'content-type: application/json' \
  -d '{"was_accurate": false, "corrected_condition_slug": "psoriasis", "comment": "Plaques were more silvery/scaly than eczema."}'
```
`422` if `corrected_condition_slug` isn't in the catalogue. `403` if a
`patient` tries to give feedback on someone else's analysis.

---

## Step 10 (optional) — Browse the condition catalogue (public, no auth)

`GET /v1/conditions` and `GET /v1/conditions/{slug}`

```bash
curl -s localhost:8000/v1/conditions
curl -s localhost:8000/v1/conditions?category=neoplastic
curl -s localhost:8000/v1/conditions/melanoma_suspected
```

Useful for building a "learn more" screen independent of any analysis.

---

## Step 11 (optional) — Download the original photo

`GET /v1/images/{id}/download-url` mints a short-lived signed URL; the actual
bytes are served by the second, unauthenticated endpoint (the signature *is*
the access token, same pattern as an S3 pre-signed URL).

```bash
curl -s localhost:8000/v1/images/$IMAGE_ID/download-url -H "Authorization: Bearer $TOKEN"
# {"url": "/v1/images/raw/<user_id>/<sha256>?expires=...&signature=...", "expires_in": 900}

curl -s "localhost:8000$(above url)" -o downloaded.jpg
```

---

## Step 12 (optional) — Delete a photo (right to erasure)

`DELETE /v1/images/{id}` — soft-deletes the row and **hard-deletes the stored
bytes**. Existing analyses that reference it are kept (for the user's own
history) but the image can no longer be re-analysed or re-downloaded.

```bash
curl -s -X DELETE localhost:8000/v1/images/$IMAGE_ID -H "Authorization: Bearer $TOKEN" -w '%{http_code}\n'
# 204
```

---

## End-to-end in one script

```bash
BASE=localhost:8000
EMAIL="patient$RANDOM@example.com"

curl -s $BASE/v1/auth/register -H 'content-type: application/json' \
  -d "{\"email\":\"$EMAIL\",\"password\":\"supersecret1\"}" >/dev/null

TOKEN=$(curl -s $BASE/v1/auth/login -H 'content-type: application/json' \
  -d "{\"email\":\"$EMAIL\",\"password\":\"supersecret1\"}" | python3 -c 'import sys,json;print(json.load(sys.stdin)["access_token"])')

for c in image_storage ai_processing; do
  curl -s $BASE/v1/consents -H "Authorization: Bearer $TOKEN" \
    -H 'content-type: application/json' -d "{\"consent_type\":\"$c\"}" >/dev/null
done

IMAGE_ID=$(curl -s $BASE/v1/images -H "Authorization: Bearer $TOKEN" \
  -F "file=@skin.jpg" -F "body_site=forearm" | python3 -c 'import sys,json;print(json.load(sys.stdin)["id"])')

curl -s $BASE/v1/analyses -H "Authorization: Bearer $TOKEN" \
  -H 'content-type: application/json' \
  -d "{\"image_id\":\"$IMAGE_ID\",\"questionnaire\":{\"itch\":true,\"duration_days\":14}}" | python3 -m json.tool
```

---

## Endpoint index

| # | Method & path | Auth | Purpose |
|---|---|---|---|
| 0 | `GET /health`, `GET /health/ready` | none | liveness / readiness |
| 1 | `POST /v1/auth/register` | none | create account |
| 2 | `POST /v1/auth/login` | none | get JWT |
| 3 | `GET /v1/auth/me` | bearer | whoami |
| 4 | `GET/POST /v1/consents` | bearer | read/grant consent |
| 5 | `POST /v1/images` | bearer | upload photo |
| 5b | `GET /v1/images`, `GET /v1/images/{id}` | bearer | list / inspect photos |
| 6 | `POST /v1/analyses` | bearer | run the pipeline |
| 7 | `GET /v1/analyses/{id}` | bearer | fetch one result |
| 8 | `GET /v1/analyses` | bearer | history |
| 9 | `POST /v1/analyses/{id}/feedback` | bearer | rate / correct |
| 10 | `GET /v1/conditions`, `GET /v1/conditions/{slug}` | none | catalogue |
| 11 | `GET /v1/images/{id}/download-url`, `GET /v1/images/raw/...` | bearer / signed | fetch bytes |
| 12 | `DELETE /v1/images/{id}` | bearer | erase |

Full schemas, status codes, and *why* each field exists: [DESIGN.md §7–8](DESIGN.md#7-api--purpose-of-each-endpoint).
