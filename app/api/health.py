from datetime import UTC, datetime

from fastapi import APIRouter

router = APIRouter()


@router.get("/health")
def get_health():
    return {
        "status": "ok",
        "service": "nutria-ia",
        "timestamp": datetime.now(UTC).isoformat(),
    }
