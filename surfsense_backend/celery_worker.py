"""Celery worker startup script."""

from app.celery_app import celery_app

if __name__ == "__main__":
    # Start the Celery worker
    celery_app.start()
