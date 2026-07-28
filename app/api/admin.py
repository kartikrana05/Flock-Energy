from fastapi import APIRouter

from app.dependencies import get_consumption_cache, get_dt_cache, get_meter_cache

router = APIRouter(prefix="/admin", tags=["admin"])


@router.post("/cache/clear")
def clear_cache() -> dict:
    get_meter_cache().clear()
    get_dt_cache().clear()
    get_consumption_cache().clear()
    return {"status": "cleared"}
