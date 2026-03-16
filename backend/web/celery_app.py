from celery import Celery

from ..config import (
    CELERY_BROKER_URL,
    CELERY_RESULT_BACKEND,
    CELERY_TASK_QUEUE,
)

celery_app = Celery(
    "audio_video_project",
    broker=CELERY_BROKER_URL,
    backend=CELERY_RESULT_BACKEND,
    include=["backend.web.tasks"],
)

celery_app.conf.update(
    task_default_queue=CELERY_TASK_QUEUE,
    task_track_started=True,
    worker_prefetch_multiplier=1,
    task_acks_late=True,
    broker_connection_retry_on_startup=True,
    result_expires=3600,
    accept_content=["json"],
    task_serializer="json",
    result_serializer="json",
    timezone="Asia/Shanghai",
    enable_utc=False,
)
