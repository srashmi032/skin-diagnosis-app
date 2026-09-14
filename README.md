# Skin Diagnosis App — Backend

Image-based **educational** skin assessment API. A user uploads a photo; the
service runs a quality check, an image classifier (mock by default, pluggable),
maps raw labels to a curated condition catalogue, and returns likely conditions
with confidences plus a **safety triage recommendation**.

> This software is for education and information only. It is **not a medical
> diagnosis** and does not replace a licensed clinician. See `DESIGN.md §9`.

## Quickstart

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env                     # optional; sane defaults work as-is
uvicorn app.main:app --reload
```

- Interactive docs: http://127.0.0.1:8000/docs
- On first boot it creates the SQLite schema and seeds the condition catalogue.

### Try it

```bash
# 1. register + login
curl -s localhost:8000/v1/auth/register -H 'content-type: application/json' \
  -d '{"email":"me@example.com","password":"password12345"}'
TOKEN=$(curl -s localhost:8000/v1/auth/login -H 'content-type: application/json' \
  -d '{"email":"me@example.com","password":"password12345"}' | python3 -c 'import sys,json;print(json.load(sys.stdin)["access_token"])')

# 2. consent (required before any image is stored/processed)
curl -s localhost:8000/v1/consents -H "Authorization: Bearer $TOKEN" \
  -H 'content-type: application/json' -d '{"consent_type":"image_storage"}'
curl -s localhost:8000/v1/consents -H "Authorization: Bearer $TOKEN" \
  -H 'content-type: application/json' -d '{"consent_type":"ai_processing"}'

# 3. upload a photo
curl -s localhost:8000/v1/images -H "Authorization: Bearer $TOKEN" \
  -F file=@/path/to/skin.jpg -F body_site=forearm

# 4. analyse it
curl -s localhost:8000/v1/analyses -H "Authorization: Bearer $TOKEN" \
  -H 'content-type: application/json' \
  -d '{"image_id":"<id-from-step-3>","questionnaire":{"itch":true,"duration_days":14}}'
```

## Tests

```bash
pytest
```

## Layout

```
app/
  main.py            FastAPI app factory + startup (schema + seed)
  config.py          env-driven settings (SKINDX_* )
  database.py        engine, session, declarative Base
  deps.py            DI: db session, current user, role guards
  models/            SQLAlchemy ORM models (one file per domain)
  schemas/           Pydantic request/response models
  routers/           HTTP endpoints (one file per resource)
  services/          business logic
    security.py      password hashing + JWT
    storage.py       object-storage adapter (local | s3)
    image_qc.py      pre-analysis quality gate
    inference/       classifier adapter interface + mock implementation
    triage.py        safety rules -> triage level + flags
    conditions.py    raw-label -> catalogue mapping
    analysis_service.py   orchestrates one analysis run
    seed.py          condition catalogue seed data
tests/               pytest API tests
DESIGN.md            full architecture + rationale for every table/model/API
SYSTEM_DESIGN.md     earlier product-framing doc (cosmetic-analysis variant)
```

Full design rationale — every table, model, and endpoint and why it exists — is
in [DESIGN.md](DESIGN.md). A worked, step-by-step call sequence (register →
consent → upload → analyse → feedback) with example requests/responses is in
[API_GUIDE.md](API_GUIDE.md).
