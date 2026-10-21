import logging
import time

from app.routers import clients

from fastapi import FastAPI, Request

from app import models  # noqa: F401  (importing registers the tables)
from app.config import settings
from app.database import Base, engine
from app.logger import setup_logging

setup_logging()
logger = logging.getLogger(__name__)

Base.metadata.create_all(bind=engine)

app = FastAPI(title=settings.app_name)

app.include_router(clients.router)

@app.middleware("http")
async def log_requests(request: Request, call_next):
    start = time.perf_counter()
    response = await call_next(request)
    ms = (time.perf_counter() - start) * 1000
    logger.info("%s %s -> %s (%.1f ms)", request.method, request.url.path, response.status_code, ms)
    return response


@app.get("/health")
def health():
    return {"status": "ok"}