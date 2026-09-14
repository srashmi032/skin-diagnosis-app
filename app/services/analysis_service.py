"""Orchestrates one analysis run.

Currently synchronous (fine for the mock adapter). For a real model, move
``run_analysis`` behind a task queue: the POST handler creates the row with
status=pending and enqueues; a worker calls this function. The DB shape does not
change.
"""

from __future__ import annotations

import time
from datetime import date, datetime, timezone

from sqlalchemy.orm import Session

from app.config import get_settings
from app.models.analysis import AnalysisPrediction, AnalysisRequest, TriageFlag
from app.models.enums import AnalysisStatus, TriageLevel
from app.models.image import SkinImage
from app.models.user import User
from app.services import conditions as condition_svc
from app.services.inference import get_adapter
from app.services.storage import get_storage
from app.services.triage import ResolvedPrediction, evaluate


def _age_years(dob: date | None) -> int | None:
    if not dob:
        return None
    today = date.today()
    return today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))


def run_analysis(db: Session, analysis: AnalysisRequest) -> AnalysisRequest:
    settings = get_settings()
    image: SkinImage = analysis.image
    user: User = analysis.user

    analysis.status = AnalysisStatus.running
    analysis.started_at = datetime.now(timezone.utc)
    db.flush()

    started = time.perf_counter()
    try:
        data = get_storage().load(image.storage_key)
        adapter = get_adapter(settings.inference_adapter)
        raw = adapter.predict(
            data,
            context={
                "body_site": image.body_site,
                "questionnaire": analysis.questionnaire or {},
            },
        )
        analysis.inference_adapter = adapter.name
        analysis.model_version = adapter.model_version

        resolved: list[ResolvedPrediction] = []
        for rank, rp in enumerate(raw, start=1):
            condition = condition_svc.resolve_label(db, rp.label)
            db.add(
                AnalysisPrediction(
                    analysis_id=analysis.id,
                    condition_id=condition.id if condition else None,
                    raw_label=rp.label,
                    confidence=rp.confidence,
                    rank=rank,
                    is_primary=rank == 1,
                    mapped_ok=condition is not None,
                )
            )
            resolved.append(ResolvedPrediction(rp.label, rp.confidence, condition))

        image_ok = bool((image.quality_report or {}).get("passed", True))
        outcome = evaluate(
            resolved,
            analysis.questionnaire,
            image_quality_passed=image_ok,
            patient_age_years=_age_years(user.date_of_birth),
        )
        analysis.triage_level = outcome.level
        analysis.triage_rationale = outcome.rationale
        for fd in outcome.flags:
            db.add(
                TriageFlag(
                    analysis_id=analysis.id,
                    code=fd.code,
                    level=fd.level,
                    message=fd.message,
                )
            )

        analysis.status = (
            AnalysisStatus.referred
            if outcome.level == TriageLevel.urgent
            else AnalysisStatus.completed
        )
    except Exception as exc:  # noqa: BLE001
        analysis.status = AnalysisStatus.failed
        analysis.error_detail = f"{type(exc).__name__}: {exc}"
    finally:
        analysis.latency_ms = int((time.perf_counter() - started) * 1000)
        analysis.completed_at = datetime.now(timezone.utc)
        analysis.disclaimer_version = settings.policy_version
        db.flush()

    return analysis
