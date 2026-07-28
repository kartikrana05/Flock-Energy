from datetime import datetime

import httpx
from fastapi import APIRouter, HTTPException, Query

from app.dependencies import get_consumption_cache
from app.models.consumption import EnergyReading, EnergyReadingList

router = APIRouter(prefix="/meters", tags=["consumption"])


@router.get("/{meter_id}/consumption", response_model=EnergyReadingList)
def get_meter_consumption(
    meter_id: str,
    start: datetime | None = Query(None, description="only readings at or after this timestamp"),
    end: datetime | None = Query(None, description="only readings at or before this timestamp"),
    page: int = Query(1, ge=1),
    page_size: int = Query(100, ge=1, le=5000),
) -> EnergyReadingList:
    cache = get_consumption_cache()
    try:
        raw_readings = cache.get(meter_id)
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code == 404:
            raise HTTPException(status_code=404, detail=f"meter {meter_id} not found")
        raise HTTPException(status_code=502, detail="portal request failed")

    readings = [EnergyReading.from_portal(r) for r in raw_readings]
    if start:
        readings = [r for r in readings if r.timestamp >= start]
    if end:
        readings = [r for r in readings if r.timestamp <= end]

    total = len(readings)
    offset = (page - 1) * page_size
    page_items = readings[offset : offset + page_size]

    return EnergyReadingList(data=page_items, total=total, page=page, page_size=page_size)
