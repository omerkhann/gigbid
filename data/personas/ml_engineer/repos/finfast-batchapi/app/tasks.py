from celery import Celery
import time

celery_app = Celery(
    "tasks",
    broker=os.getenv("CELERY_BROKER_URL", "redis://redis:6379/0"),
    backend=os.getenv("CELERY_RESULT_BACKEND", "redis://redis:6379/0")
)

@celery_app.task
def predict_task(data):
    # Simulate model inference
    time.sleep(0.1)
    return [len(str(d)) for d in data]
