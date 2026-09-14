"""Safety layer: turn raw predictions + symptoms + image QC into a triage level.

Design stance: over-refer rather than under-refer. Anything uncertain or anything
resembling a malignancy escalates, regardless of how confident the classifier is.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.config import get_settings
from app.models.condition import SkinCondition
from app.models.enums import FlagCode, TriageLevel

_LEVEL_RANK = {TriageLevel.routine: 0, TriageLevel.soon: 1, TriageLevel.urgent: 2}


@dataclass
class ResolvedPrediction:
    raw_label: str
    confidence: float
    condition: SkinCondition | None


@dataclass
class FlagDraft:
    code: FlagCode
    level: TriageLevel
    message: str


@dataclass
class TriageOutcome:
    level: TriageLevel
    rationale: str
    flags: list[FlagDraft]


def evaluate(
    predictions: list[ResolvedPrediction],
    questionnaire: dict | None,
    image_quality_passed: bool,
    patient_age_years: int | None,
) -> TriageOutcome:
    settings = get_settings()
    q = questionnaire or {}
    flags: list[FlagDraft] = []

    top = predictions[0] if predictions else None

    # 1. Low confidence / nothing mapped.
    if top is None or not top.condition:
        flags.append(
            FlagDraft(
                FlagCode.low_confidence,
                TriageLevel.soon,
                "The image could not be matched to a known pattern with confidence.",
            )
        )
    elif top.confidence < settings.referral_confidence_floor:
        flags.append(
            FlagDraft(
                FlagCode.low_confidence,
                TriageLevel.soon,
                f"Top result confidence ({top.confidence:.0%}) is below the "
                f"{settings.referral_confidence_floor:.0%} threshold for a self-care suggestion.",
            )
        )

    # 2. Any malignancy-type condition with non-trivial probability.
    for p in predictions:
        if p.condition and p.condition.is_referral_trigger and p.confidence >= 0.10:
            flags.append(
                FlagDraft(
                    FlagCode.possible_malignancy,
                    TriageLevel.urgent,
                    f"A pattern that can indicate skin cancer ({p.condition.display_name}) "
                    "was among the possibilities. This needs in-person evaluation.",
                )
            )
            break

    # 3. Symptom red flags.
    if q.get("recent_change"):
        flags.append(
            FlagDraft(
                FlagCode.rapid_change_reported,
                TriageLevel.urgent,
                "You reported a recent change in size, shape, or colour.",
            )
        )
    if q.get("bleeding"):
        flags.append(
            FlagDraft(
                FlagCode.bleeding_or_nonhealing,
                TriageLevel.urgent,
                "You reported bleeding or a sore that will not heal.",
            )
        )
    if q.get("spreading") and (q.get("duration_days") or 0) <= 3:
        flags.append(
            FlagDraft(
                FlagCode.widespread_or_systemic,
                TriageLevel.soon,
                "A rapidly spreading rash can need prompt treatment.",
            )
        )

    # 4. Image quality.
    if not image_quality_passed:
        flags.append(
            FlagDraft(
                FlagCode.poor_image_quality,
                TriageLevel.routine,
                "Image quality was low; retake in bright, even light and re-scan.",
            )
        )

    # 5. Pediatric caution.
    if patient_age_years is not None and patient_age_years < 12:
        flags.append(
            FlagDraft(
                FlagCode.pediatric_caution,
                TriageLevel.soon,
                "For young children, have a clinician confirm any skin finding.",
            )
        )

    # Resolve overall level: max of flag levels, else the condition's default.
    if flags:
        level = max((f.level for f in flags), key=_LEVEL_RANK.get)
        rationale = " ".join(f.message for f in flags)
    elif top and top.condition:
        level = top.condition.default_triage_level
        rationale = (
            f"Best match: {top.condition.display_name} ({top.confidence:.0%} confidence). "
            f"{top.condition.when_to_see_doctor or ''}".strip()
        )
    else:
        level = TriageLevel.soon
        rationale = "Unable to assess; please see a clinician."

    return TriageOutcome(level=level, rationale=rationale, flags=flags)
