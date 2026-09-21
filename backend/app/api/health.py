from fastapi import APIRouter

from app.config import settings

router = APIRouter()


@router.get("/health")
def health() -> dict:
    return {"status": "ok", "service": "elite-sistem-api", "env": settings.env}
