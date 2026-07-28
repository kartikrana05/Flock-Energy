from datetime import datetime

from pydantic import BaseModel


class EnergyReading(BaseModel):
    timestamp: datetime
    kwh: float
    kvah: float
    volt_r: float

    @classmethod
    def from_portal(cls, raw: dict) -> "EnergyReading":
        return cls(
            timestamp=datetime.strptime(raw["timestamp"], "%d/%m/%Y %H:%M"),
            kwh=float(raw["kwh"]),
            kvah=float(raw["kvah"]),
            volt_r=float(raw["voltR"]),
        )


class EnergyReadingList(BaseModel):
    data: list[EnergyReading]
    total: int
    page: int
    page_size: int
