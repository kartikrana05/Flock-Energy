from pydantic import BaseModel


class Dt(BaseModel):
    dt_code: str
    name: str
    feeder_code: str
    capacity_kva: int

    @classmethod
    def from_portal(cls, raw: dict) -> "Dt":
        return cls(
            dt_code=raw["code"],
            name=raw["name"],
            feeder_code=raw["feederCode"],
            capacity_kva=raw["capacityKva"],
        )


class DtList(BaseModel):
    data: list[Dt]
    total: int
    page: int
    page_size: int
