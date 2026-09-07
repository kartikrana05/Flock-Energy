import json
import re

from pydantic import BaseModel

_LABEL_RE = re.compile(r"^(.*) \(([^)]+)\)$")

# PascalCase ORM column -> the display label the `data` shape uses for the same field.
_CLASS_DATA_LABELS = {
    "MeterId": "Meter ID",
    "SerialNo": "Serial No",
    "Make": "Make",
    "PhaseType": "Phase Type",
    "InstallationStatus": "Installation Status",
    "InstallationType": "Installation Type",
}


def _normalize_detail(detail: dict) -> dict:
    """Flatten either meter-detail shape into one {display label: value} dict.

    The portal serves detail two ways, split 238/165 across the fleet:
    `data` is the label/value table its own UI renders, while `classData` is a
    raw dump of the installed_meter row - PascalCase keys, and doubly encoded,
    so the value is a JSON *string* that has to be parsed again. Both carry
    the same six fields; see PROTOCOL.md.
    """
    if "data" in detail:
        return {row["parameterName"]: row["parameterValue"] for row in detail["data"]}
    if "classData" in detail:
        inner = json.loads(detail["classData"])["installed_meter"]
        return {label: inner[column] for column, label in _CLASS_DATA_LABELS.items()}
    raise ValueError(f"unrecognized meter detail shape: {sorted(detail)}")


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
        fields = _normalize_detail(resolved["detail"])
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
