from fastapi import APIRouter, Query

from app.dependencies import get_dt_cache
from app.models.network import Dt, DtList

router = APIRouter(prefix="/network", tags=["network"])

SEARCH_FIELDS = ("dt_code", "name", "feeder_code")


@router.get("/dts", response_model=DtList)
def list_dts(
    search: str = Query("", description="matches DT code, name, or feeder code"),
    dt_code: str | None = Query(None),
    name: str | None = Query(None),
    feeder_code: str | None = Query(None),
    capacity_kva: int | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=1000),
) -> DtList:
    cache = get_dt_cache()
    dts = [Dt.from_portal(raw) for raw in cache.get_all()]

    if search:
        needle = search.lower()
        dts = [d for d in dts if any(needle in getattr(d, f).lower() for f in SEARCH_FIELDS)]

    exact_filters = {"dt_code": dt_code, "name": name, "feeder_code": feeder_code}
    for field, value in exact_filters.items():
        if value:
            dts = [d for d in dts if getattr(d, field).lower() == value.lower()]
    if capacity_kva is not None:
        dts = [d for d in dts if d.capacity_kva == capacity_kva]

    total = len(dts)
    start = (page - 1) * page_size
    page_items = dts[start : start + page_size]

    return DtList(data=page_items, total=total, page=page, page_size=page_size)
