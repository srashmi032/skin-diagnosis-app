"""Controlled vocabularies used across models and the API.

Keeping these as enums (stored as strings, ``native_enum=False``) means the
database rejects any value outside the closed set — important for the condition
category and triage level, which have safety implications.
"""

from __future__ import annotations

from enum import StrEnum


class UserRole(StrEnum):
    patient = "patient"
    clinician = "clinician"  # verified professional who can review/correct results
    admin = "admin"


class ConsentType(StrEnum):
    image_storage = "image_storage"          # keep the uploaded photo at rest
    ai_processing = "ai_processing"          # run automated analysis on it
    research_use = "research_use"            # use de-identified data to improve models
    share_with_clinician = "share_with_clinician"


class ImageStatus(StrEnum):
    uploaded = "uploaded"          # bytes stored, not yet checked
    quality_failed = "quality_failed"
    ready = "ready"               # passed QC, analysable
    deleted = "deleted"          # soft-deleted, bytes purged


class AnalysisStatus(StrEnum):
    pending = "pending"
    running = "running"
    completed = "completed"
    referred = "referred"        # finished, but routed to "see a professional"
    failed = "failed"


class ConditionCategory(StrEnum):
    inflammatory = "inflammatory"     # acne, eczema, psoriasis, rosacea
    infectious = "infectious"         # tinea, impetigo, herpes, warts
    pigmentary = "pigmentary"         # melasma, vitiligo, PIH
    neoplastic = "neoplastic"         # nevi, keratoses, suspected malignancy
    autoimmune = "autoimmune"
    cosmetic = "cosmetic"             # dryness, pores, fine lines
    other = "other"


class TriageLevel(StrEnum):
    routine = "routine"   # self-care fine; see a clinician if it persists
    soon = "soon"         # book a clinician within a few weeks
    urgent = "urgent"     # seek prompt in-person medical evaluation


class FlagCode(StrEnum):
    low_confidence = "low_confidence"
    possible_malignancy = "possible_malignancy"
    rapid_change_reported = "rapid_change_reported"
    bleeding_or_nonhealing = "bleeding_or_nonhealing"
    widespread_or_systemic = "widespread_or_systemic"
    poor_image_quality = "poor_image_quality"
    pediatric_caution = "pediatric_caution"
