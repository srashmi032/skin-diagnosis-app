"""Seed the SkinCondition catalogue.

Educational summaries only. ``when_to_see_doctor`` copy is deliberately
conservative. Malignancy entries are ``is_referral_trigger=True`` so they can
never produce a self-care recommendation.
"""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.condition import SkinCondition
from app.models.enums import ConditionCategory, TriageLevel

CONDITIONS: list[dict] = [
    {
        "slug": "acne_vulgaris",
        "display_name": "Acne",
        "aliases": ["acne", "pimples", "acne_vulgaris"],
        "category": ConditionCategory.inflammatory,
        "summary": "Blocked, inflamed hair follicles producing blackheads, whiteheads, papules, or cysts, usually on the face, chest, or back.",
        "common_symptoms": ["blackheads", "whiteheads", "tender red bumps", "occasional cysts"],
        "typical_body_sites": ["face", "chest", "upper back", "shoulders"],
        "self_care_guidance": "Gentle cleanser twice daily, non-comedogenic moisturiser, OTC benzoyl peroxide or adapalene. Avoid picking.",
        "when_to_see_doctor": "See a clinician if it scars, is painful/cystic, or does not improve after 8–12 weeks of OTC care.",
        "default_triage_level": TriageLevel.routine,
    },
    {
        "slug": "atopic_dermatitis",
        "display_name": "Eczema (atopic dermatitis)",
        "aliases": ["eczema", "atopic_eczema", "dermatitis"],
        "category": ConditionCategory.inflammatory,
        "summary": "A chronic, itchy, relapsing inflammation of the skin with dry, scaly, sometimes weeping patches, often in skin folds.",
        "common_symptoms": ["intense itch", "dry rough skin", "red or darkened patches", "flares and remissions"],
        "typical_body_sites": ["inner elbows", "behind knees", "hands", "face", "neck"],
        "self_care_guidance": "Frequent fragrance-free emollients, short lukewarm showers, OTC hydrocortisone 1% for flares, identify triggers.",
        "when_to_see_doctor": "See a clinician for widespread, infected (crusted, oozing, painful), or sleep-disrupting eczema.",
        "default_triage_level": TriageLevel.routine,
    },
    {
        "slug": "psoriasis",
        "display_name": "Psoriasis",
        "aliases": ["plaque_psoriasis"],
        "category": ConditionCategory.autoimmune,
        "summary": "An immune-driven condition causing well-defined, thickened plaques with silvery scale, commonly on extensor surfaces and scalp.",
        "common_symptoms": ["thick scaly plaques", "silvery scale", "itch or soreness", "nail pitting"],
        "typical_body_sites": ["elbows", "knees", "scalp", "lower back"],
        "self_care_guidance": "Thick emollients, coal tar or salicylic acid preparations, sunlight in moderation, avoid skin trauma.",
        "when_to_see_doctor": "See a clinician to confirm the diagnosis and for anything beyond a few small patches, or if joints ache.",
        "default_triage_level": TriageLevel.soon,
    },
    {
        "slug": "rosacea",
        "display_name": "Rosacea",
        "aliases": ["acne_rosacea"],
        "category": ConditionCategory.inflammatory,
        "summary": "Persistent central-face redness with flushing, visible vessels, and sometimes acne-like bumps; eyes can be involved.",
        "common_symptoms": ["facial flushing", "persistent redness", "visible blood vessels", "burning or stinging"],
        "typical_body_sites": ["cheeks", "nose", "forehead", "chin"],
        "self_care_guidance": "Daily broad-spectrum SPF, gentle skincare, identify and avoid triggers (heat, alcohol, spicy food).",
        "when_to_see_doctor": "See a clinician for prescription options; seek care promptly if the eyes feel gritty or vision changes.",
        "default_triage_level": TriageLevel.routine,
    },
    {
        "slug": "seborrheic_dermatitis",
        "display_name": "Seborrheic dermatitis",
        "aliases": ["dandruff", "seborrhoeic_dermatitis", "sebderm"],
        "category": ConditionCategory.inflammatory,
        "summary": "Flaky, greasy scale with mild redness in oil-rich areas, driven by Malassezia yeast and skin oil.",
        "common_symptoms": ["greasy yellowish flakes", "mild itch", "redness in skin folds"],
        "typical_body_sites": ["scalp", "eyebrows", "sides of nose", "chest"],
        "self_care_guidance": "Antifungal shampoo (ketoconazole, zinc pyrithione, selenium sulfide) left on a few minutes, 2–3x/week.",
        "when_to_see_doctor": "See a clinician if it spreads, does not respond, or a baby has thick widespread involvement.",
        "default_triage_level": TriageLevel.routine,
    },
    {
        "slug": "contact_dermatitis",
        "display_name": "Contact dermatitis",
        "aliases": ["allergic_contact_dermatitis", "irritant_contact_dermatitis"],
        "category": ConditionCategory.inflammatory,
        "summary": "A localised itchy, red, sometimes blistering reaction where the skin touched an irritant or allergen.",
        "common_symptoms": ["itch", "redness in a defined area", "small blisters", "dry cracking skin"],
        "typical_body_sites": ["hands", "face", "eyelids", "anywhere contacted"],
        "self_care_guidance": "Identify and remove the trigger, wash the area, OTC hydrocortisone and cool compresses, emollients.",
        "when_to_see_doctor": "See a clinician for facial/genital involvement, large areas, or no improvement in 1–2 weeks.",
        "default_triage_level": TriageLevel.routine,
    },
    {
        "slug": "tinea_corporis",
        "display_name": "Ringworm (tinea)",
        "aliases": ["ringworm", "tinea", "dermatophytosis", "tinea_corporis"],
        "category": ConditionCategory.infectious,
        "summary": "A superficial fungal infection forming an expanding ring with a scaly, raised edge and clearer centre.",
        "common_symptoms": ["ring-shaped scaly patch", "itch", "central clearing", "slow outward spread"],
        "typical_body_sites": ["trunk", "limbs", "groin", "feet", "scalp"],
        "self_care_guidance": "OTC topical antifungal (terbinafine, clotrimazole) for 2–4 weeks, keep the area dry, don't share towels.",
        "when_to_see_doctor": "See a clinician for scalp involvement, many patches, or no improvement after 2 weeks of treatment.",
        "default_triage_level": TriageLevel.routine,
    },
    {
        "slug": "urticaria",
        "display_name": "Hives (urticaria)",
        "aliases": ["hives", "wheals", "nettle_rash"],
        "category": ConditionCategory.inflammatory,
        "summary": "Transient itchy raised welts that appear and fade within hours, often from an allergic or physical trigger.",
        "common_symptoms": ["itchy raised welts", "welts move around", "individual spots last <24h"],
        "typical_body_sites": ["anywhere", "trunk", "limbs"],
        "self_care_guidance": "Non-drowsy OTC antihistamine, avoid known triggers, cool compresses.",
        "when_to_see_doctor": "Call emergency services for swelling of lips/tongue/throat or breathing difficulty. See a clinician if hives last > 6 weeks.",
        "default_triage_level": TriageLevel.routine,
    },
    {
        "slug": "melasma",
        "display_name": "Melasma",
        "aliases": ["chloasma", "pregnancy_mask"],
        "category": ConditionCategory.pigmentary,
        "summary": "Symmetric brown to grey-brown patches on sun-exposed facial skin, linked to UV, hormones, and genetics.",
        "common_symptoms": ["symmetric facial pigmentation", "worsens with sun", "no itch or scale"],
        "typical_body_sites": ["cheeks", "forehead", "upper lip", "bridge of nose"],
        "self_care_guidance": "Strict daily broad-spectrum SPF 50 and physical shade; OTC azelaic acid or niacinamide may help slowly.",
        "when_to_see_doctor": "See a clinician or dermatologist for prescription lightening agents and to confirm the diagnosis.",
        "default_triage_level": TriageLevel.routine,
    },
    {
        "slug": "vitiligo",
        "display_name": "Vitiligo",
        "aliases": ["leucoderma"],
        "category": ConditionCategory.pigmentary,
        "summary": "Loss of pigment producing well-defined milky-white patches, often symmetric, from autoimmune melanocyte destruction.",
        "common_symptoms": ["sharply defined white patches", "symmetric spread", "no scale or itch"],
        "typical_body_sites": ["hands", "face", "around eyes and mouth", "elbows", "knees"],
        "self_care_guidance": "Sun protection of depigmented skin (it burns easily); cosmetic camouflage if desired.",
        "when_to_see_doctor": "See a clinician to confirm and discuss treatment; earlier treatment responds better.",
        "default_triage_level": TriageLevel.soon,
    },
    {
        "slug": "wart",
        "display_name": "Common wart",
        "aliases": ["verruca", "verruca_vulgaris", "hpv_wart"],
        "category": ConditionCategory.infectious,
        "summary": "A rough, firm skin growth caused by human papillomavirus, sometimes with tiny black dots (clotted vessels).",
        "common_symptoms": ["rough raised bump", "black pinpoints", "can be tender on pressure points"],
        "typical_body_sites": ["hands", "fingers", "feet", "knees"],
        "self_care_guidance": "OTC salicylic acid daily for weeks; many warts resolve on their own within 1–2 years.",
        "when_to_see_doctor": "See a clinician for painful, rapidly growing, facial/genital, or diagnostically uncertain lesions.",
        "default_triage_level": TriageLevel.routine,
    },
    {
        "slug": "cold_sore",
        "display_name": "Cold sore (herpes labialis)",
        "aliases": ["herpes_labialis", "fever_blister", "hsv1"],
        "category": ConditionCategory.infectious,
        "summary": "A recurrent cluster of small painful blisters on or near the lips from herpes simplex virus, healing in 7–10 days.",
        "common_symptoms": ["tingling then blisters", "grouped vesicles", "crusting", "recurs in the same spot"],
        "typical_body_sites": ["lip border", "around the mouth"],
        "self_care_guidance": "OTC docosanol or topical antiviral at the tingle stage, don't touch/share, sun protection of lips.",
        "when_to_see_doctor": "See a clinician for frequent outbreaks, sores lasting > 2 weeks, eye involvement, or a weakened immune system.",
        "default_triage_level": TriageLevel.routine,
    },
    {
        "slug": "benign_nevus",
        "display_name": "Mole (benign nevus)",
        "aliases": ["mole", "nevus", "naevus", "nv"],
        "category": ConditionCategory.neoplastic,
        "summary": "A common benign cluster of pigment cells: usually small, uniform in colour, with a regular border and stable over time.",
        "common_symptoms": ["uniform brown colour", "regular round/oval border", "stable size", "symmetric"],
        "typical_body_sites": ["anywhere on the skin"],
        "self_care_guidance": "Photograph and monitor. Learn the ABCDE rule (Asymmetry, Border, Colour, Diameter, Evolving).",
        "when_to_see_doctor": "See a clinician promptly for any mole that changes, itches, bleeds, or looks different from your others.",
        "default_triage_level": TriageLevel.routine,
    },
    {
        "slug": "actinic_keratosis",
        "display_name": "Actinic keratosis",
        "aliases": ["solar_keratosis", "ak"],
        "category": ConditionCategory.neoplastic,
        "summary": "A rough, scaly patch from years of sun damage. It is pre-cancerous — a small fraction progress to squamous cell carcinoma.",
        "common_symptoms": ["persistent rough sandpapery patch", "pink/brown", "on sun-exposed skin", "may be tender"],
        "typical_body_sites": ["face", "ears", "scalp", "back of hands", "forearms"],
        "self_care_guidance": "Rigorous sun protection. Do not treat as a cosmetic spot.",
        "when_to_see_doctor": "See a clinician for evaluation and treatment; these should be assessed in person.",
        "default_triage_level": TriageLevel.soon,
        "is_referral_trigger": True,
    },
    {
        "slug": "basal_cell_carcinoma_suspected",
        "display_name": "Possible basal cell carcinoma",
        "aliases": ["bcc", "basal_cell_carcinoma", "rodent_ulcer"],
        "category": ConditionCategory.neoplastic,
        "summary": "The most common skin cancer. Often a pearly or waxy bump, a non-healing sore, or a flat scar-like area on sun-exposed skin. Rarely spreads but grows locally.",
        "common_symptoms": ["pearly translucent bump", "visible vessels", "sore that heals then returns", "central crust or ulcer"],
        "typical_body_sites": ["face", "nose", "ears", "neck", "scalp"],
        "self_care_guidance": None,
        "when_to_see_doctor": "See a doctor or dermatologist promptly for an in-person exam and likely biopsy.",
        "default_triage_level": TriageLevel.urgent,
        "is_referral_trigger": True,
    },
    {
        "slug": "melanoma_suspected",
        "display_name": "Possible melanoma",
        "aliases": ["melanoma", "malignant_melanoma", "mel"],
        "category": ConditionCategory.neoplastic,
        "summary": "A serious skin cancer arising from pigment cells. Warning signs: asymmetry, irregular border, multiple colours, diameter > 6 mm, or any change over time.",
        "common_symptoms": ["asymmetric mole", "irregular or notched border", "varied colours", "growth or change", "itch or bleeding"],
        "typical_body_sites": ["back", "legs", "any pigmented lesion"],
        "self_care_guidance": None,
        "when_to_see_doctor": "See a doctor or dermatologist urgently for an in-person exam. Early melanoma is highly treatable; do not wait.",
        "default_triage_level": TriageLevel.urgent,
        "is_referral_trigger": True,
    },
]


def seed_conditions(db: Session, *, force: bool = False) -> int:
    """Insert missing conditions. Returns how many were added."""
    existing = {
        row for row in db.scalars(select(SkinCondition.slug)).all()
    }
    added = 0
    for data in CONDITIONS:
        if data["slug"] in existing and not force:
            continue
        if data["slug"] in existing:
            db.query(SkinCondition).filter_by(slug=data["slug"]).delete()
        db.add(
            SkinCondition(
                reference_url="https://www.aad.org/public/diseases",
                **data,
            )
        )
        added += 1
    db.commit()
    return added


def condition_count(db: Session) -> int:
    return db.scalar(select(func.count()).select_from(SkinCondition)) or 0
