"""Import every model so SQLAlchemy's mapper registry is complete on load."""

from app.models.analysis import (
    AnalysisFeedback,
    AnalysisPrediction,
    AnalysisRequest,
    TriageFlag,
)
from app.models.audit import AuditLog
from app.models.condition import SkinCondition
from app.models.image import SkinImage
from app.models.user import ConsentRecord, User

__all__ = [
    "AnalysisFeedback",
    "AnalysisPrediction",
    "AnalysisRequest",
    "AuditLog",
    "ConsentRecord",
    "SkinCondition",
    "SkinImage",
    "TriageFlag",
    "User",
]
