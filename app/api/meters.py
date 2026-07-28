from fastapi import APIRouter, HTTPException, Query

from app.dependencies import get_meter_cache, get_meter_detail_cache
from app.models.meters import Meter, MeterDetail, MeterList
from app.portal.sveltekit import PageDataError, resolve_leaf_data

router = APIRouter(prefix="/meters", tags=["meters"])

SEARCH_FIELDS = ("meter_id", "serial_no")


@router.get("", response_model=MeterList)
def list_meters(
    search: str = Query("", description="matches meter number or serial number"),
    meter_id: str | None = Query(None),
    serial_no: str | None = Query(None),
    make: str | None = Query(None),
    phase_type: str | None = Query(None),
    status: str | None = Query(None),
    dt_code: str | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=1000),
) -> MeterList:
    cache = get_meter_cache()
    meters = [Meter.from_portal(raw) for raw in cache.get_all()]

    if search:
        needle = search.lower()
        meters = [m for m in meters if any(needle in getattr(m, f).lower() for f in SEARCH_FIELDS)]

    exact_filters = {
        "meter_id": meter_id,
        "serial_no": serial_no,
        "make": make,
        "phase_type": phase_type,
        "status": status,
        "dt_code": dt_code,
    }
    for field, value in exact_filters.items():
        if value:
            meters = [m for m in meters if getattr(m, field).lower() == value.lower()]

    total = len(meters)
    start = (page - 1) * page_size
    page_items = meters[start : start + page_size]

    return MeterList(data=page_items, total=total, page=page, page_size=page_size)


@router.get("/{meter_id}", response_model=MeterDetail)
def get_meter_detail(meter_id: str) -> MeterDetail:
    cache = get_meter_detail_cache()
    payload = cache.get(meter_id)

    try:
        resolved = resolve_leaf_data(payload)
    except PageDataError as exc:
        raise HTTPException(status_code=exc.status, detail=exc.message)

    return MeterDetail.from_page_data(resolved)
