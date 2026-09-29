"""Celery tasks. Currently one: run the analysis pipeline off the request thread.

The task opens its own DB session — it may run in a separate worker process,
so it cannot share the request's session. It commits its own results
independently of the request that enqueued it (the AnalysisRequest row is
already committed as ``status=pending`` before this task is queued).
"""

from __future__ import annotations

import logging

from app.celery_app import celery_app
from app.database import SessionLocal
from app.models.analysis import AnalysisRequest
from app.services.analysis_service import run_analysis

logger = logging.getLogger("skindx")


@celery_app.task(name="analyses.run_analysis", bind=True, max_retries=2, default_retry_delay=10)
def run_analysis_task(self, analysis_id: str) -> None:
    with SessionLocal() as db:
        analysis = db.get(AnalysisRequest, analysis_id)
        if analysis is None:
            logger.warning("run_analysis_task: analysis %s not found", analysis_id)
            return
        try:
            run_analysis(db, analysis)
            db.commit()
        except Exception as exc:  # noqa: BLE001
            db.rollback()
            logger.exception("run_analysis_task failed for %s", analysis_id)
            raise self.retry(exc=exc)
