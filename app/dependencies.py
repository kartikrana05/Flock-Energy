from functools import lru_cache

from app.config import settings
from app.portal.cache import KeyedCache, PagedCache
from app.portal.client import PortalClient


@lru_cache
def get_portal_client() -> PortalClient:
    return PortalClient(
        base_url=settings.portal_base_url,
        username=settings.portal_username,
        password=settings.portal_password,
    )


@lru_cache
def get_meter_cache() -> PagedCache:
    client = get_portal_client()
    return PagedCache(
        lambda page: client.search_meters(q="", page=page),
        ttl_seconds=settings.cache_ttl_seconds,
        enabled=settings.cache_enabled,
    )


@lru_cache
def get_dt_cache() -> PagedCache:
    client = get_portal_client()
    return PagedCache(
        lambda page: client.list_dts(page=page),
        ttl_seconds=settings.cache_ttl_seconds,
        enabled=settings.cache_enabled,
    )


@lru_cache
def get_consumption_cache() -> KeyedCache:
    client = get_portal_client()
    return KeyedCache(
        lambda meter_id: client.get_energy(meter_id),
        ttl_seconds=settings.cache_ttl_seconds,
        enabled=settings.cache_enabled,
    )


@lru_cache
def get_meter_detail_cache() -> KeyedCache:
    client = get_portal_client()
    return KeyedCache(
        lambda meter_id: client.get_meter_page_data(meter_id),
        ttl_seconds=settings.cache_ttl_seconds,
        enabled=settings.cache_enabled,
    )
