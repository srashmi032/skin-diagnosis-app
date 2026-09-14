# SkinSense — System Design

*(Working name — rename freely.)*

## 0. Product framing (read this first — it shapes every decision below)

This app does **cosmetic skin analysis**, not medical diagnosis:

- The AI/image-analysis layer only ever outputs **cosmetic concern categories** — dryness, oiliness, visible pores, dark spots, fine lines, uneven tone, mild redness — and maps them to **OTC skincare product suggestions** (cleanser, serum, sunscreen, moisturizer).
- It **never** outputs a medical/disease label (e.g. "eczema", "psoriasis", "melanoma") and **never** prescribes or suggests prescription-only treatment. That line is enforced in the product-copy layer, not just by intent — see §5.
- Anything that looks like it needs real medical attention is a **hand-off point**: the app's job is to make booking a licensed dermatologist (in-person or virtual) as frictionless as possible, not to substitute for one.
- Every analysis result carries a visible disclaimer: *"This is a cosmetic suggestion, not a medical diagnosis. Consult a dermatologist for any persistent, painful, or changing skin concern."*

This framing matters legally (avoids operating as an unlicensed medical device/practice) and product-wise (it's the actual value prop: fast cosmetic guidance + easy escalation to a real professional).

## 1. Feature list

### A. Skin analysis (cosmetic only)
- Upload a photo (or a short guided set: front, left, right) of face/skin area
- On-device or server-side image quality check (lighting, blur, face detection) before analysis
- Cosmetic concern detection → tags with confidence + severity (mild/moderate/noticeable)
- Skin-type quiz (oily/dry/combination/sensitive) to complement image analysis
- Personalized routine: cleanser → treatment (serum) → moisturizer → SPF, with 2-3 product options per step, filterable by budget/ingredient preferences (fragrance-free, non-comedogenic, etc.)
- Progress tracking: photo timeline, re-scan every N weeks, trend view ("redness reduced 20% over 4 weeks")
- Ingredient/ "why this product" explainability (builds trust, keeps it educational rather than prescriptive)

### B. Dermatologist marketplace
- Dermatologist profiles: credentials, license number (verified at onboarding), specialties, languages, in-person clinic location(s) and/or virtual-only, ratings/reviews
- Search/filter by concern, location, availability, price, language
- **Booking**
  - In-person: clinic calendar, slot selection, address/directions, reminders
  - Virtual: video-consult slot booking, integrates with a video provider (Twilio Video / Agora / Daily.co — don't build WebRTC signaling from scratch)
- **Pre-visit context handoff**: with the patient's consent, the dermatologist sees the same cosmetic-analysis history/photos the app generated — saves the patient re-explaining
- **In-consult**: chat + video; dermatologist can issue actual prescriptions/medical notes *inside their own clinical workflow* — this app does not generate or store prescriptions itself, it hands off to the dermatologist's tooling (or a lightweight prescription-note feature scoped and reviewed separately, since e-prescribing has real regulatory requirements per country/state)
- Post-visit: consultation summary, follow-up booking, payment receipt

### C. Platform-wide
- Auth (patient accounts, dermatologist accounts — separate roles/permissions)
- Payments (consultation fees; product links can be affiliate/referral rather than the app selling inventory, to avoid becoming a pharmacy/retailer with its own compliance burden)
- Notifications (appointment reminders, routine check-in nudges, message alerts)
- Admin/back-office: dermatologist license verification queue, content moderation, dispute handling
- Privacy controls: photo deletion, data export, consent management (see §6)

## 2. High-level architecture

```
                     ┌────────────┐    ┌─────────────┐
                     │  Mobile /  │    │   Web app   │
                     │  app client│    │             │
                     └─────┬──────┘    └──────┬──────┘
                           │                  │
                           └────────┬─────────┘
                                    │  HTTPS
                            ┌───────▼────────┐
                            │   API Gateway   │  (auth, rate limit, routing)
                            └───────┬────────┘
        ┌───────────┬───────────┬──┴──────┬────────────┬──────────────┐
        │           │           │         │            │              │
   ┌────▼───┐  ┌────▼─────┐┌────▼────┐┌───▼──────┐┌────▼──────┐┌──────▼─────┐
   │  Auth  │  │  Skin    ││ Product ││ Dermat.  ││ Booking / ││  Payments  │
   │  Svc   │  │ Analysis ││  Catalog││ Directory││ Scheduling││    Svc     │
   └────┬───┘  └────┬─────┘└────┬────┘└───┬──────┘└────┬──────┘└──────┬─────┘
        │           │           │         │            │              │
        │      ┌────▼─────┐     │         │      ┌─────▼──────┐       │
        │      │  ML/CV   │     │         │      │  Video     │       │
        │      │ inference│     │         │      │  provider  │       │
        │      │ (async)  │     │         │      │ (Twilio/   │       │
        │      └────┬─────┘     │         │      │  Agora)    │       │
        │           │           │         │      └────────────┘       │
        └───────────┴─────┬─────┴─────────┴────────────┬──────────────┘
                           │                             │
                    ┌──────▼───────┐             ┌───────▼────────┐
                    │  Postgres    │             │ Object storage  │
                    │ (relational) │             │ (photos, S3-    │
                    │              │             │  compatible)    │
                    └──────────────┘             └────────────────┘
                           │
                    ┌──────▼───────┐
                    │ Redis + queue │  (background jobs: async ML
                    │  (Celery/etc) │   inference, notifications,
                    └──────────────┘   reminders, reconciliation)
```

Each box in the middle row is a service boundary (can start as modules in one FastAPI app — see §7 — and split out later if load demands it; no need to over-engineer microservices on day one).

## 3. Core services

| Service | Responsibility |
|---|---|
| Auth | Patient + dermatologist accounts, JWT sessions, role-based access, dermatologist license verification workflow |
| Skin Analysis | Accepts photo upload → quality check → enqueues async inference job → stores cosmetic concern tags + confidence scores, never a disease label |
| Product Catalog | Product data (category, ingredients, price, affiliate link), rule engine mapping concern-tags → routine recommendations |
| Dermatologist Directory | Profiles, credentials, specialties, search/filter, ratings |
| Booking/Scheduling | Availability calendars, slot locking, in-person vs virtual branching, reminders |
| Payments | Consultation fee capture (Stripe/Razorpay — same pattern as a standard payment integration, tokenized, no raw card data touching this backend) |
| Notifications | Push/email/SMS for appointment reminders, routine check-ins, new messages |
| Messaging | Async chat between patient and dermatologist (pre/post consult) |
| Video | Thin integration layer over a third-party video SDK for virtual consults |

## 4. Data model (high level, not exhaustive)

- **User** (patient) — profile, skin-type quiz answers, consent flags
- **Dermatologist** — credentials, license_number, license_status (pending/verified/rejected), specialties[], clinic_locations[], is_virtual_available
- **SkinScan** — user_id, photo_url(s), taken_at, quality_check_status
- **SkinAnalysisResult** — scan_id, concern_tags[] (each: label, confidence, severity), model_version — *label vocabulary is a controlled cosmetic-only list, enforced at the schema/enum level, not just convention*
- **Product** — name, category, ingredients[], price, affiliate_url, suitable_for_tags[]
- **RoutineRecommendation** — analysis_result_id, steps[] (ordered product suggestions)
- **Appointment** — patient_id, dermatologist_id, mode (in_person/virtual), slot, status, location_or_video_room
- **Consultation** — appointment_id, chat_thread_id, summary_note (dermatologist-authored), follow_up_recommended
- **Payment** — appointment_id, amount, status
- **ConsentRecord** — user_id, consent_type (photo_storage, share_with_dermatologist, marketing), granted_at, revoked_at

## 5. Where the "no medical advice" line is actually enforced

Not just a disclaimer — structurally:
1. `SkinAnalysisResult.concern_tags` uses a **closed enum** of cosmetic terms (dryness, oiliness, visible_pores, dark_spots, fine_lines, uneven_tone, mild_redness, etc.). The ML layer's raw output is mapped through this enum; anything that doesn't map cleanly gets routed to "**we recommend seeing a dermatologist**" rather than force-fit into a cosmetic label.
2. Confidence/severity thresholds: low-confidence or high-severity-looking results (e.g. anything resembling a lesion, asymmetric mole, rapid change) trip a **"see a professional" branch** instead of a product recommendation — this is a safety-first design, better to over-refer than under-diagnose.
3. Product recommendations only ever surface **OTC/cosmetic products** — no prescription-strength retinoids, no steroid creams, nothing that requires a prescription. That catalog constraint is enforced by the Product Catalog service's data, not by the recommendation logic alone.
4. Actual prescriptions happen **inside the dermatologist's own consult**, not generated by this app.

## 6. Non-functional requirements

- **Privacy/consent**: skin photos are sensitive personal data (arguably health-adjacent even if not formally PHI under a specific regulation, depending on jurisdiction). Explicit opt-in consent before storing photos or sharing with a dermatologist; easy deletion; encryption at rest and in transit; signed/expiring URLs for photo access, never public buckets.
- **Dermatologist verification**: license numbers checked against a registry (varies by country — e.g. NPI/state board lookups in the US) before an account can accept bookings. This is a manual/admin-reviewed queue for v1, automatable later.
- **Availability/scalability**: ML inference is async (queue-based) so photo upload never blocks on model latency; booking/payment paths need standard idempotency (same pattern as any payment integration — see the `payment-service-saas` project for the idempotency-key convention already established).
- **Compliance posture**: this is not a licensed telehealth platform by itself — it's a marketplace/scheduling layer connecting patients to *already-licensed* dermatologists, who carry the clinical responsibility. Get real legal review before launch on video-consult recording, e-prescribing, and cross-state/cross-country licensing rules — those vary a lot and this doc isn't a substitute for that review.

## 7. Suggested tech stack (matches the stack already used in your other projects this session)

- **Backend**: Python, FastAPI (async), SQLAlchemy 2.0 + Alembic, Pydantic v2
- **DB**: PostgreSQL (JSONB for flexible fields like concern_tags, ingredient lists)
- **Storage**: S3-compatible object storage for photos, signed URLs
- **Queue/background jobs**: Celery + Redis (async ML inference, notifications, reminders)
- **ML/CV**: start with a hosted vision API (e.g. a general image-classification/face-analysis API) behind an internal interface, so it can be swapped for a custom-trained model later without touching the rest of the app — same "adapter" pattern as a payment-processor abstraction
- **Video**: Twilio Video / Agora / Daily.co SDK, thin wrapper service
- **Payments**: Stripe/Razorpay, tokenized, same pattern as any payment integration — never touch raw card data

## 8. Phased roadmap

**Phase 1 (draft, this session)**: Upload photo → mocked/rule-based cosmetic analysis → product suggestions. No real ML yet, no auth, single endpoint — just to prove the shape of the interaction.

**Phase 2**: Auth, real user accounts, persist scans/results, skin-type quiz, routine builder, product catalog.

**Phase 3**: Swap mock analysis for a real vision-model integration behind the adapter interface; add photo progress-tracking.

**Phase 4**: Dermatologist directory + booking (in-person first, simpler than video).

**Phase 5**: Virtual consultations (video integration), messaging, payments for consults.

**Phase 6**: Admin/verification tooling, notifications, polish.
