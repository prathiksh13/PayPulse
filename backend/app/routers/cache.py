from fastapi import APIRouter

from ..utils.cache import clear_cache

router = APIRouter(tags=["cache"])


@router.post("/cache/invalidate")
def invalidate_cache():
    """Drop process-wide TTL caches so every page reads fresh rows immediately.

    Called by the frontend after mutating actions (test payment, retry, refund,
    anomaly resolution, webhook ingestion) to keep all dashboards consistent.
    """
    clear_cache()
    return {"ok": True, "cleared": True}