import re

from pydantic import BaseModel

_LABEL_RE = re.compile(r"^(.*) \(([^)]+)\)$")


class Meter(BaseModel):
    meter_id: str
    serial_no: str
    make: str
    phase_type: str
    status: str
    dt_code: str

    @classmethod
    def from_portal(cls, raw: dict) -> "Meter":
        return cls(
            meter_id=raw["meterId"],
            serial_no=raw["serialNo"],
            make=raw["make"],
            phase_type=raw["phaseType"],
            status=raw["installStatus"],
            dt_code=raw["dtCode"],
        )


class MeterList(BaseModel):
    data: list[Meter]
    total: int
    page: int
    page_size: int


class HierarchyLevel(BaseModel):
    name: str
    code: str

    @classmethod
    def from_label(cls, label: str) -> "HierarchyLevel":
        match = _LABEL_RE.match(label)
        if not match:
            return cls(name=label, code="")
        return cls(name=match.group(1), code=match.group(2))


class MeterDetail(BaseModel):
    meter_id: str
    serial_no: str
    make: str
    phase_type: str
    status: str
    installation_type: str
    zone: HierarchyLevel
    circle: HierarchyLevel
    division: HierarchyLevel
    subdivision: HierarchyLevel
    substation: HierarchyLevel
    feeder: HierarchyLevel
    dt: HierarchyLevel

    @classmethod
    def from_page_data(cls, resolved: dict) -> "MeterDetail":
        fields = {row["parameterName"]: row["parameterValue"] for row in resolved["detail"]["data"]}
        hierarchy = resolved["hierarchy"]

        return cls(
            meter_id=fields["Meter ID"],
            serial_no=fields["Serial No"],
            make=fields["Make"],
            phase_type=fields["Phase Type"],
            status=fields["Installation Status"],
            installation_type=fields["Installation Type"],
            zone=HierarchyLevel.from_label(hierarchy["Zone"]),
            circle=HierarchyLevel.from_label(hierarchy["Circle"]),
            division=HierarchyLevel.from_label(hierarchy["Division"]),
            subdivision=HierarchyLevel.from_label(hierarchy["Subdivision"]),
            substation=HierarchyLevel.from_label(hierarchy["Sub Station"]),
            feeder=HierarchyLevel.from_label(hierarchy["Feeder"]),
            dt=HierarchyLevel.from_label(hierarchy["DT"]),
        )
