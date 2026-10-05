from fastapi import APIRouter, Query

from schemas.admin import (AdminStatus, BusItem, BusPatch, DataSourceRequest, DriverItem, DriverPatch, Page,
                           RouteItem, StationItem)
from services import admin

router = APIRouter(prefix="/admin", tags=["admin"])

PageParam = Query(1, ge=1)
PageSizeParam = Query(20, ge=1, le=100, alias="pageSize")
SearchParam = Query(None, max_length=100, description="Case-insensitive search in any field")


@router.get("/status", response_model=AdminStatus)
def status():
    return admin.status()


@router.post("/data-source", response_model=AdminStatus)
def data_source(req: DataSourceRequest):
    return admin.switch_source(req.data_source)


@router.get("/drivers", response_model=Page[DriverItem])
def drivers(page: int = PageParam, page_size: int = PageSizeParam, q: str | None = SearchParam):
    return admin.list_drivers(page, page_size, q)


@router.get("/buses", response_model=Page[BusItem])
def buses(page: int = PageParam, page_size: int = PageSizeParam, q: str | None = SearchParam):
    return admin.list_buses(page, page_size, q)


@router.get("/stations", response_model=Page[StationItem])
def stations(page: int = PageParam, page_size: int = PageSizeParam, q: str | None = SearchParam):
    return admin.list_stations(page, page_size, q)


@router.get("/routes", response_model=Page[RouteItem])
def routes(page: int = PageParam, page_size: int = PageSizeParam, q: str | None = SearchParam):
    return admin.list_routes(page, page_size, q)


@router.patch("/drivers/{driver_id}", response_model=DriverItem)
def patch_driver(driver_id: str, patch: DriverPatch):
    return admin.patch_driver(driver_id, patch)


@router.patch("/buses/{bus_id}", response_model=BusItem)
def patch_bus(bus_id: str, patch: BusPatch):
    return admin.patch_bus(bus_id, patch)


@router.post("/reset", response_model=AdminStatus)
def reset():
    return admin.reset()
