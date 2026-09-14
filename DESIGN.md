# Skin Diagnosis App — Backend Design

Companion to the code in `app/`. It explains **what each table, model, service,
and API endpoint is for and why it exists**. For product-level framing of an
alternative cosmetic-only variant, see `SYSTEM_DESIGN.md`; this document
describes the backend as actually built: an **educational condition classifier
with safety triage**.

---

## 1. Purpose & scope

**Goal.** Let a person photograph a skin concern and receive:

1. an **educational** ranked list of skin conditions the image resembles, each
   with a confidence score and plain-language information, and
2. a **triage recommendation** — routine self-care, see a clinician soon, or seek
   prompt in-person care — derived from the predictions, a short symptom
   questionnaire, and image quality.

**Explicitly out of scope.**

- It is **not a medical diagnosis** and is not a regulated medical device
  workflow. Every result carries a disclaimer and, where relevant, a referral.
- It does **not** prescribe, and does not generate prescriptions.
- It does not (yet) do longitudinal lesion tracking, teledermatology, or
  payments — see the roadmap in §12.

**Design stance: over-refer, never under-refer.** Whenever the system is
uncertain, or anything resembling a malignancy appears, or the user reports a red
flag symptom, the result escalates to a referral instead of a self-care tip.
This is enforced structurally (see §9), not just in copy.

---

## 2. Technology choices

| Concern | Choice | Why |
|---|---|---|
| Language / framework | Python + FastAPI | Async-capable, first-class OpenAPI docs, Pydantic validation, matches the ML ecosystem the classifier will live in |
| ORM / migrations | SQLAlchemy 2.0 (typed) + Alembic | Portable across SQLite (dev) and PostgreSQL (prod); explicit schema |
| DB | SQLite dev / PostgreSQL prod | `JSON` columns for flexible fields (quality reports, questionnaires, prediction metadata) |
| Auth | JWT (HS256), PBKDF2-HMAC-SHA256 password hashing (stdlib) | No native-extension dependency; swap to Argon2id / asymmetric JWT in prod |
| Image storage | Pluggable adapter — local disk (dev) / S3 (prod) | The app depends only on an interface; signed URLs, never public buckets |
| Inference | Pluggable adapter — deterministic **mock** now | Ship the whole pipeline before the model exists; swap one class later |
| Validation | Pydantic v2 schemas | Request/response contracts decoupled from ORM rows |

Everything is environment-driven via `Settings` (`app/config.py`), prefix
`SKINDX_`, with local-dev defaults so the app boots with zero configuration.

---

## 3. High-level architecture

```
             ┌──────────┐  HTTPS + Bearer JWT
   client ──▶│  FastAPI  │
             │  routers  │
             └────┬──────┘
        ┌─────────┼──────────────┬───────────────┬──────────────┐
        ▼         ▼              ▼               ▼              ▼
    security   storage      image_qc        inference       triage
    (JWT/hash) (local/S3)   (quality gate)  (mock|real)     (safety rules)
        │         │              │               │              │
        └─────────┴────┬─────────┴───────┬───────┴──────────────┘
                       ▼                 ▼
                 analysis_service   conditions (label→catalogue)
                       │
                       ▼
             ┌───────────────────┐        ┌────────────────────┐
             │   PostgreSQL      │        │  Object storage    │
             │  (relational)     │        │  (image bytes)     │
             └───────────────────┘        └────────────────────┘
```

The middle row are **services** — plain modules today, each behind a narrow
interface so any one can become a separate process later without touching
callers.

### Request lifecycle — `POST /v1/analyses`

1. **Auth** — `get_current_user` validates the JWT, loads the `User`.
2. **Ownership + preconditions** — the referenced `SkinImage` must belong to the
   caller and must not have failed QC.
3. **Persist intent** — an `AnalysisRequest` row is created with
   `status=pending` and the adapter/model version stamped for reproducibility.
4. **Run pipeline** (`analysis_service.run_analysis`):
   - load image bytes from storage,
   - `inference.predict()` → `list[RawPrediction]`,
   - `conditions.resolve_label()` maps each raw label to a `SkinCondition`
     (or `None` → `mapped_ok=False`),
   - persist one `AnalysisPrediction` per guess,
   - `triage.evaluate()` → `TriageLevel` + `TriageFlag`s from predictions +
     questionnaire + image quality + patient age,
   - `status` becomes `completed` or, if triage is `urgent`, `referred`.
5. **Audit** — an `AuditLog` row records the action.
6. **Respond** — the full `AnalysisRead` including predictions, flags, triage
   rationale, and the disclaimer text.

Today step 4 runs **synchronously** (the mock is instant). For a real model,
step 3 returns `202` and step 4 moves to a queue worker — the database shape does
not change.

---

## 4. Data model overview

```
users ─┬─< consent_records
       ├─< skin_images ─┬─< analysis_requests ─┬─< analysis_predictions >─ skin_conditions
       │                │                      ├─< triage_flags
       │                │                      └─< analysis_feedback >──── skin_conditions
       └─< analysis_requests (also FK user_id, for "my history" queries)

skin_conditions   (reference catalogue, no inbound FKs except SET NULL links)
audit_logs        (append-only, no FKs — deliberately decoupled)
```

Conventions across every table:

- **String UUID primary keys** (`id`) — safe to expose in URLs, portable across
  engines, no sequential enumeration.
- **`created_at` / `updated_at`** timestamps (except `audit_logs`, which only has
  `created_at` because rows are immutable).
- **Closed enums stored as strings** (`native_enum=False`) — the DB rejects any
  value outside the vocabulary, which matters for `condition.category` and
  `triage_level`.
- **Soft-delete for user content** (`skin_images.deleted_at`); **hard-delete of
  the underlying bytes** on erasure requests.

---

## 5. Tables & models — purpose of each

### 5.1 `users` — `app/models/user.py :: User`

**Why.** Every image and analysis belongs to an account; role drives
authorization.

| Column | Purpose |
|---|---|
| `email`, `hashed_password` | Credentials. Password stored as `pbkdf2_sha256$iterations$salt$hash`. |
| `full_name` | Display only. |
| `role` | `patient` \| `clinician` \| `admin`. Gates endpoints (`require_role`). A `clinician` can leave corrective feedback on any analysis; a `patient` only on their own. |
| `is_active` | Soft account disable without deleting history. |
| `date_of_birth` | Optional. Feeds the **pediatric caution** triage rule (age < 12). |
| `skin_type` | Optional Fitzpatrick / oily-dry context; reserved for future model conditioning and routine advice. |

Relationships: `consents`, `images`, `analyses` (all `cascade="all, delete-orphan"`
so deleting a user removes their data).

### 5.2 `consent_records` — `ConsentRecord`

**Why.** Skin photos are sensitive personal data. We must be able to prove the
user opted in **before** anything was stored or processed, and honour
withdrawal.

| Column | Purpose |
|---|---|
| `consent_type` | `image_storage`, `ai_processing`, `research_use`, `share_with_clinician`. |
| `granted` | Current decision. |
| `granted_at` / `revoked_at` | Timestamps for the grant/withdrawal. |
| `policy_version` | Which privacy-policy version the user agreed to. |

Design: **new row per decision** rather than mutating one row — the latest row
per `(user_id, consent_type)` is authoritative (`consents.has_consent`). This
keeps a defensible history. `POST /v1/images` refuses unless both `image_storage`
and `ai_processing` are currently granted.

### 5.3 `skin_images` — `SkinImage`

**Why.** Metadata and storage pointer for one uploaded photo. **Image bytes are
never in the database** — they live in object storage under `storage_key`
(`{user_id}/{sha256}`).

| Column | Purpose |
|---|---|
| `storage_backend`, `storage_key` | Where the bytes are. Backend recorded so a later storage migration is unambiguous. |
| `content_type`, `byte_size` | Validated on upload; `byte_size` also feeds abuse/rate limits. |
| `checksum_sha256` | Content-addressing: dedupe, integrity, and it *is* the storage key suffix. |
| `width`, `height` | From Pillow during QC; `NULL` if Pillow absent. |
| `body_site` | User-supplied (`face`, `forearm`, `scalp`…). A real model conditions on this; triage copy uses it. |
| `captured_at` | When the photo was taken (vs. uploaded). |
| `status` | `uploaded` → `ready` \| `quality_failed` → `deleted`. `POST /v1/analyses` refuses a `quality_failed` image. |
| `quality_report` (JSON) | Full QC output: magic-byte match, dimensions, exposure/contrast heuristics, warnings, failure reason. Stored so support and model teams can see *why* an image was rejected. |
| `deleted_at` | Soft-delete marker; bytes are hard-deleted at the same time. |

### 5.4 `skin_conditions` — `SkinCondition`  *(reference catalogue)*

**Why.** This is the **controlled vocabulary** for everything the system says to
a user. A raw model label is only ever surfaced after it maps to a row here;
anything unmapped is treated as "uncertain → refer". Tuning the product
(educational copy, which findings force referral, default urgency) is a
**data edit here**, not a code change.

| Column | Purpose |
|---|---|
| `slug` | Stable identifier used by the label mapper and the API (`/v1/conditions/{slug}`). |
| `display_name` | Human label shown in results. |
| `aliases` (JSON) | Alternate model-native labels and lay terms (`"eczema"`, `"nv"`, `"ringworm"`) the mapper also accepts. |
| `category` | `inflammatory` \| `infectious` \| `pigmentary` \| `neoplastic` \| `autoimmune` \| `cosmetic` \| `other`. Enables filtered browsing and category-level analytics. |
| `summary`, `common_symptoms`, `typical_body_sites` | Educational content. |
| `self_care_guidance` | OTC-only guidance. **`NULL` for malignancy entries** — there is deliberately no self-care copy to show. |
| `when_to_see_doctor` | Escalation guidance, appended to the triage rationale. |
| `reference_url` | Link to an authoritative patient-education source. |
| `default_triage_level` | Baseline urgency when no flag fires. |
| `is_referral_trigger` | `True` for suspected melanoma / BCC / actinic keratosis. Any non-trivial probability of such a condition forces an `urgent` triage flag and blocks self-care copy. |
| `is_active` | Retire a condition without deleting historical predictions that point to it. |

Seed data: 16 common conditions in `app/services/seed.py` (acne, eczema,
psoriasis, rosacea, seborrheic/contact dermatitis, tinea, urticaria, melasma,
vitiligo, wart, cold sore, benign nevus, actinic keratosis, suspected BCC,
suspected melanoma).

### 5.5 `analysis_requests` — `AnalysisRequest`

**Why.** One run of the pipeline against one image. Holds the **outcome
envelope**; the individual guesses and flags are child rows.

| Column | Purpose |
|---|---|
| `user_id`, `image_id` | Owner and subject. `image_id` FK is `ON DELETE RESTRICT` — you cannot hard-delete an image row that has analyses; you soft-delete it. |
| `status` | `pending` → `running` → `completed` \| `referred` \| `failed`. `referred` = finished but routed to in-person care. |
| `inference_adapter`, `model_version` | **Reproducibility** — exactly which model produced this result, so results can be re-evaluated when the model changes. |
| `questionnaire` (JSON) | Optional symptom answers (`itch`, `pain`, `duration_days`, `spreading`, `bleeding`, `recent_change`, `prior_similar`). Feeds triage. |
| `triage_level` | Derived: `routine` \| `soon` \| `urgent`. |
| `triage_rationale` | Human-readable explanation shown to the user. |
| `disclaimer_version` | Which disclaimer wording the user saw. |
| `error_detail` | Populated on `failed`. |
| `started_at`, `completed_at`, `latency_ms` | Observability / SLOs. |

Relationships: `predictions` (ordered by `rank`), `flags`, `feedback` — all
cascade-delete with the request.

### 5.6 `analysis_predictions` — `AnalysisPrediction`

**Why.** One ranked condition guess. Separate table (not a JSON blob) so we can
query "how often does the model say melanoma", join to conditions, and compute
per-condition accuracy from feedback.

| Column | Purpose |
|---|---|
| `analysis_id` | Parent. |
| `condition_id` | FK to the catalogue, **nullable**, `ON DELETE SET NULL`. Null when the raw label didn't map. |
| `raw_label` | The exact string the model emitted — kept even when it maps, so we can audit the mapping and measure drift. |
| `confidence` | `0..1`. |
| `rank` | `1` = most likely. |
| `is_primary` | Convenience flag for `rank == 1`. |
| `mapped_ok` | `False` → this guess is uncertain; triage treats a `False` top result as "refer". |

### 5.7 `triage_flags` — `TriageFlag`

**Why.** Explicit, queryable record of *why* a result was escalated or
downplayed. Shown to the user; also lets us monitor how often each safety rule
fires.

| Column | Purpose |
|---|---|
| `code` | `low_confidence`, `possible_malignancy`, `rapid_change_reported`, `bleeding_or_nonhealing`, `widespread_or_systemic`, `poor_image_quality`, `pediatric_caution`. |
| `level` | The urgency this particular flag implies. |
| `message` | User-facing sentence. |

The analysis's overall `triage_level` is the **maximum** level across all flags
(`urgent` > `soon` > `routine`); with no flags it falls back to the primary
condition's `default_triage_level`.

### 5.8 `analysis_feedback` — `AnalysisFeedback`

**Why.** Two audiences: patients ("was this helpful?") and clinicians ("was this
correct, and what was it actually?"). Drives quality dashboards and builds a
labelled dataset for training the real model.

| Column | Purpose |
|---|---|
| `submitted_by_id`, `submitter_role` | Who gave it; role stored denormalised because a user's role can change later. |
| `helpfulness_rating` | 1–5, patient-facing. |
| `was_accurate` | Clinician judgment. |
| `corrected_condition_id` | Clinician's actual assessment (FK to catalogue, `SET NULL`). |
| `comment` | Free text (≤ 2000 chars). |

### 5.9 `audit_logs` — `AuditLog`

**Why.** Sensitive-data access trail for security review and incident response:
`image.upload`, `image.download`, `image.delete`, `analysis.create`,
(extensible). **Append-only** — application code only ever inserts. No foreign
keys, so purging user data never cascades away the audit trail; `actor_id` /
`resource_id` are plain indexed strings.

| Column | Purpose |
|---|---|
| `actor_id` | Who acted (nullable — signed-URL downloads have no bearer session). |
| `action`, `resource_type`, `resource_id` | What happened to what. |
| `ip_address`, `user_agent` | Request provenance. |
| `context` (JSON) | Action-specific extras (e.g. `{"quality_passed": false}`). |

---

## 6. Services — purpose of each

| Module | Responsibility | Key seam |
|---|---|---|
| `services/security.py` | Password hash/verify (PBKDF2-HMAC-SHA256), JWT issue/decode | Replaceable with Argon2id / RS256 without touching routers |
| `services/storage.py` | Read/write/delete image bytes; issue & verify signed URLs | `Storage` `Protocol`; `LocalStorage` now, `S3Storage` later — config switch only |
| `services/image_qc.py` | Reject wrong-type / tiny / unreadable images; warn on exposure & contrast | Degrades gracefully if Pillow is missing (header checks only) |
| `services/inference/base.py` | `InferenceAdapter` protocol + `RawPrediction` dataclass | **The one seam** between app and pixels |
| `services/inference/mock.py` | Deterministic hash-seeded classifier over the seed vocabulary, including malignancy labels | Same bytes ⇒ same output (repeatable demos/tests) |
| `services/inference/registry.py` | `get_adapter(name)` factory | Add `hosted_vision` / `custom` here |
| `services/triage.py` | Turn predictions + questionnaire + QC + age into `TriageLevel` + flags | Pure function, unit-testable in isolation |
| `services/conditions.py` | Map a raw model label → `SkinCondition` via slug/alias | Unmapped ⇒ `mapped_ok=False` ⇒ triage escalates |
| `services/analysis_service.py` | Orchestrate one run; own transaction boundaries and timing | Move body to a queue worker for real models |
| `services/seed.py` | Condition catalogue seed / upsert | Edit data here to tune the product |
| `services/audit.py` | Append one `AuditLog` row (caller commits) | — |

---

## 7. API — purpose of each endpoint

Base path `/v1`. All routes except health, `raw` image download, and the
condition catalogue require `Authorization: Bearer <jwt>`.

### Health

| Method & path | Purpose |
|---|---|
| `GET /` | Service name, docs link, disclaimer. |
| `GET /health` | Liveness. |
| `GET /health/ready` | Readiness — runs `SELECT 1`. |

### Auth — `/v1/auth`

| Method & path | Purpose | Notes |
|---|---|---|
| `POST /register` | Create a patient account | 409 on duplicate email; returns `UserRead` |
| `POST /login` | Exchange credentials for a JWT | `role` embedded as a claim; `expires_in` in seconds |
| `GET /me` | Current user profile | — |

### Consent — `/v1/consents`

| Method & path | Purpose | Notes |
|---|---|---|
| `GET ` | List the caller's consent history | newest first |
| `POST ` | Record a grant or withdrawal | one row per decision; **must** grant `image_storage` + `ai_processing` before uploading |

### Images — `/v1/images`

| Method & path | Purpose | Notes |
|---|---|---|
| `POST ` | Upload a photo (`multipart/form-data`: `file`, optional `body_site`, `captured_at`) | Enforces consent, size, type; runs QC; stores bytes; writes audit row. 413 too large, 422 empty. |
| `GET ` | List the caller's non-deleted images | — |
| `GET /{id}` | One image's metadata + `quality_report` | 404 if not owned |
| `GET /{id}/download-url` | Mint a short-lived **signed URL** for the bytes | TTL from `SKINDX_SIGNED_URL_TTL_SECONDS` |
| `GET /raw/{user}/{sha}?expires=&signature=` | Serve the bytes | **No bearer** — the HMAC signature is the capability, same model as an S3 pre-signed URL; verifies expiry + signature; writes `image.download` audit row |
| `DELETE /{id}` | Right-to-erasure: soft-delete the row, **hard-delete the bytes** | 204; audit row |

### Analyses — `/v1/analyses`

| Method & path | Purpose | Notes |
|---|---|---|
| `POST ` | Run the pipeline on an image (`{image_id, questionnaire?}`) | 404 unknown/unowned image; 422 if image failed QC; returns full `AnalysisRead` incl. predictions, flags, triage, disclaimer |
| `GET ` | The caller's analysis history (summaries) | newest first |
| `GET /{id}` | One full analysis result | 404 if not owned |
| `POST /{id}/feedback` | Rate a result / (clinician) correct it | patients: own analyses only; clinicians: any. `corrected_condition_slug` validated against the catalogue |

### Conditions — `/v1/conditions`

| Method & path | Purpose | Notes |
|---|---|---|
| `GET ?category=` | Browse the educational catalogue | public; optional category filter |
| `GET /{slug}` | One condition's full educational entry | public; 404 unknown slug |

---

## 8. Schemas (`app/schemas/`)

Pydantic models are the **API contract**, deliberately separate from ORM rows so
storage columns can change without breaking clients and vice-versa.

| Schema | Role |
|---|---|
| `UserRegister` / `UserLogin` / `Token` | Auth I/O; password `min_length=8` |
| `UserRead` | Safe user projection (no hash) |
| `ConsentCreate` / `ConsentRead` | Consent I/O |
| `ImageRead` / `ImageDownloadUrl` | Image metadata + signed-URL response |
| `ConditionRead` | Catalogue entry projection |
| `AnalysisCreate` + nested `Questionnaire` | Analysis request; questionnaire keys are validated, not free-form |
| `PredictionRead` / `TriageFlagRead` | Nested result rows, incl. embedded `ConditionRead` |
| `AnalysisSummary` / `AnalysisRead` | List vs. detail projections; `AnalysisRead.disclaimer` filled from settings by the router |
| `FeedbackCreate` / `FeedbackRead` | Feedback I/O; `FeedbackCreate` requires at least one field |

---

## 9. Where the "not a diagnosis" line is enforced — structurally

1. **Closed condition vocabulary.** Results can only reference `skin_conditions`
   rows. A raw model label that doesn't map is `mapped_ok=False`, and a
   `mapped_ok=False` **top** prediction makes triage return `soon` with a
   `low_confidence` flag rather than showing a guess.
2. **Confidence floor.** Top confidence below `SKINDX_REFERRAL_CONFIDENCE_FLOOR`
   (default 0.45) ⇒ `low_confidence` flag, no self-care suggestion.
3. **Malignancy is a hard referral.** Any prediction whose condition has
   `is_referral_trigger=True` with confidence ≥ 0.10 ⇒ `possible_malignancy`
   flag at `urgent`; those catalogue rows have `self_care_guidance = NULL`.
4. **Symptom red flags.** `recent_change` or `bleeding` in the questionnaire ⇒
   `urgent`, independent of what the classifier said.
5. **Overall level = max of all flag levels.** Escalation always wins.
6. **Every response carries the disclaimer** and, on `urgent`, `status` is
   `referred`.
7. **No prescription data model exists** — the app cannot represent one.

---

## 10. Non-functional requirements

- **Privacy.** Consent-gated storage/processing; signed expiring URLs, never
  public buckets; `DELETE` hard-purges bytes; `research_use` is a separate,
  independently-revocable consent.
- **Security.** Bearer JWT with role claims; per-row ownership checks on every
  image/analysis route; path-traversal guard in `LocalStorage`; audit trail on
  sensitive actions; passwords never logged or returned.
- **Reproducibility.** `inference_adapter` + `model_version` stamped on every
  analysis; `raw_label` retained alongside the mapped condition.
- **Observability.** `latency_ms`, `started_at`/`completed_at` per analysis;
  `error_detail` on failure; structured audit log.
- **Scalability path.** Inference is the only slow step and is already isolated
  in `analysis_service.run_analysis` — move it to a Celery/RQ/arq worker,
  return `202`, and let clients poll `GET /v1/analyses/{id}` until `status`
  leaves `pending`/`running`. No schema change.
- **Portability.** SQLite ↔ PostgreSQL via SQLAlchemy; `JSON` columns work on
  both; enums are string-checked, not DB-native.

---

## 11. Migrations

Dev uses `Base.metadata.create_all()` on startup for convenience. Production
should use **Alembic**:

```bash
alembic init migrations
# set sqlalchemy.url from app.config, target_metadata = app.database.Base.metadata
alembic revision --autogenerate -m "initial schema"
alembic upgrade head
```

Then remove the `init_db()` call from `lifespan`.

---

## 12. Roadmap

| Phase | Scope |
|---|---|
| **1 (done)** | Auth, consent, image upload + QC, mock inference, label mapping, triage, feedback, condition catalogue, audit log, tests |
| **2** | Real inference adapter (hosted vision API or self-hosted CNN) behind `InferenceAdapter`; async queue + `202`; S3 storage backend |
| **3** | Longitudinal tracking (re-scan the same body site, trend view); richer questionnaire; clinician review console |
| **4** | Dermatologist directory + booking hand-off (see `SYSTEM_DESIGN.md §B`) |
| **5** | Notifications, rate limiting, admin/moderation tooling, Alembic in CI, load testing |

---

## 13. Known limitations (current build)

- Mock classifier only — predictions are not clinically meaningful yet.
- Inference is synchronous and in-process.
- No rate limiting / quota enforcement beyond per-file size.
- JWT has no refresh/rotation or revocation list.
- Single-region local storage; S3 adapter is a stub (`NotImplementedError`).
- `create_all` on startup instead of migrations.
