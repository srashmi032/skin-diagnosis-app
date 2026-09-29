"""Celery application instance — the broker/backend for async inference.

A separate worker process consumes tasks from Redis:

    celery -A app.celery_app worker --loglevel=info

``task_always_eager`` (set via ``SKINDX_CELERY_TASK_ALWAYS_EAGER``) runs tasks
synchronously in-process instead, with no Redis/worker required — the local
dev and test default (see ``.env.example`` / ``tests/conftest.py``).
"""

from __future__ import annotations

from celery import Celery

from app.config import get_settings

_settings = get_settings()

celery_app = Celery("skindx", broker=_settings.redis_url, backend=_settings.redis_url)
celery_app.conf.update(
    task_always_eager=_settings.celery_task_always_eager,
    task_eager_propagates=True,
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
)
