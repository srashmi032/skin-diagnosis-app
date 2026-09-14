from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.config import get_settings
from app.deps import get_current_user, get_db
from app.models.analysis import AnalysisFeedback, AnalysisPrediction, AnalysisRequest
from app.models.condition import SkinCondition
from app.models.enums import AnalysisStatus, ImageStatus
from app.models.image import SkinImage
from app.models.user import User
from app.schemas.analysis import AnalysisCreate, AnalysisRead, AnalysisSummary
from app.schemas.feedback import FeedbackCreate, FeedbackRead
from app.services import audit
from app.services.analysis_service import run_analysis

router = APIRouter(prefix="/v1/analyses", tags=["analyses"])


def _load_full(db: Session, analysis_id: str) -> AnalysisRequest | None:
    return db.scalar(
        select(AnalysisRequest)
        .where(AnalysisRequest.id == analysis_id)
        .options(
            selectinload(AnalysisRequest.predictions).selectinload(
                AnalysisPrediction.condition
            ),
            selectinload(AnalysisRequest.flags),
        )
    )


def _to_read(analysis: AnalysisRequest) -> AnalysisRead:
    model = AnalysisRead.model_validate(analysis)
    model.disclaimer = get_settings().disclaimer_text
    return model


@router.post("", response_model=AnalysisRead, status_code=status.HTTP_201_CREATED)
def create_analysis(
    payload: AnalysisCreate,
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> AnalysisRead:
    image = db.get(SkinImage, payload.image_id)
    if image is None or image.user_id != user.id or image.deleted_at is not None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Image not found")
    if image.status == ImageStatus.quality_failed:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "Image failed quality checks; upload a clearer photo. "
            f"Details: {(image.quality_report or {}).get('reason')}",
        )

    settings = get_settings()
    analysis = AnalysisRequest(
        user_id=user.id,
        image_id=image.id,
        status=AnalysisStatus.pending,
        inference_adapter=settings.inference_adapter,
        model_version=settings.model_version,
        questionnaire=(
            payload.questionnaire.model_dump(exclude_none=True)
            if payload.questionnaire
            else None
        ),
    )
    db.add(analysis)
    db.flush()

    # Synchronous: fine for the mock adapter. For a real model, enqueue a job
    # here and return 202 with status=pending instead (DB shape is unchanged).
    run_analysis(db, analysis)

    audit.record(
        db,
        action="analysis.create",
        resource_type="analysis_request",
        resource_id=analysis.id,
        actor_id=user.id,
        ip_address=request.client.host if request.client else None,
        context={"status": analysis.status, "triage_level": analysis.triage_level},
    )
    db.commit()
    return _to_read(_load_full(db, analysis.id))


@router.get("", response_model=list[AnalysisSummary])
def list_analyses(
    user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> list[AnalysisRequest]:
    return list(
        db.scalars(
            select(AnalysisRequest)
            .where(AnalysisRequest.user_id == user.id)
            .order_by(AnalysisRequest.created_at.desc())
        )
    )


@router.get("/{analysis_id}", response_model=AnalysisRead)
def get_analysis(
    analysis_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> AnalysisRead:
    analysis = _load_full(db, analysis_id)
    if analysis is None or analysis.user_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Analysis not found")
    return _to_read(analysis)


@router.post(
    "/{analysis_id}/feedback",
    response_model=FeedbackRead,
    status_code=status.HTTP_201_CREATED,
)
def submit_feedback(
    analysis_id: str,
    payload: FeedbackCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> AnalysisFeedback:
    analysis = db.get(AnalysisRequest, analysis_id)
    if analysis is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Analysis not found")
    if user.role == "patient" and analysis.user_id != user.id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Not your analysis")

    corrected_id = None
    if payload.corrected_condition_slug:
        cond = db.scalar(
            select(SkinCondition).where(
                SkinCondition.slug == payload.corrected_condition_slug
            )
        )
        if cond is None:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_ENTITY, "Unknown corrected_condition_slug"
            )
        corrected_id = cond.id

    fb = AnalysisFeedback(
        analysis_id=analysis.id,
        submitted_by_id=user.id,
        submitter_role=user.role,
        helpfulness_rating=payload.helpfulness_rating,
        was_accurate=payload.was_accurate,
        corrected_condition_id=corrected_id,
        comment=payload.comment,
    )
    db.add(fb)
    db.commit()
    db.refresh(fb)
    return fb
