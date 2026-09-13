from datetime import datetime, timezone

from fastapi import APIRouter

router = APIRouter()


@router.get("/health")
def get_health():
    return {
        "status": "ok",
        "service": "nutria-ia",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
