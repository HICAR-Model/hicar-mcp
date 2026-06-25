"""Core data models shared across the knowledge, validation and server layers.

These dataclasses are the in-memory representation AND the JSON artifact
representation (via ``to_dict`` / ``from_dict``), so the schema is defined
once here and reused by ``extract`` (write) and ``artifacts`` (read).
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum


class NmlType(str, Enum):
    """Inferred *data* type of a namelist option.

    Note: this is distinct from HICAR's ``type`` integer in
    ``get_nml_var_metadata`` which encodes nest-broadcast semantics
    (see ``NestSemantics``), not the value's data type.
    """

    STRING = "string"
    INT = "int"
    FLOAT = "float"
    BOOL = "bool"
    STRING_ENUM = "string_enum"  # scheme selectors with named choices
    INT_ENUM = "int_enum"        # restricted to a discrete integer set
    ARRAY = "array"
    DATE = "date"
    UNKNOWN = "unknown"


class NestSemantics(int, Enum):
    """HICAR's ``type`` field meaning for multi-nest runs."""

    UNSET = 0
    SAME_ACROSS_NESTS = 1   # one value, identical for every nest
    PER_NEST = 2            # must be set uniquely per nest


@dataclass
class EnumValue:
    """A single allowed value of an enum option.

    ``name`` is the human/string form (e.g. ``"morrison"``); ``code`` is the
    integer the model stores (e.g. ``3``). Either may be ``None`` for the
    rare case where only one form exists.
    """

    name: str | None = None
    code: int | None = None
    constant: str | None = None  # originating Fortran constant, e.g. "kMP_MORRISON"

    def to_dict(self) -> dict:
        return {"name": self.name, "code": self.code, "constant": self.constant}

    @classmethod
    def from_dict(cls, d: dict) -> "EnumValue":
        return cls(name=d.get("name"), code=d.get("code"), constant=d.get("constant"))


@dataclass
class NmlOption:
    """One namelist option, fully described."""

    name: str
    group: str = ""                 # logical group, e.g. "Physics"
    fortran_block: str = ""         # &block label, e.g. "physics"
    description: str = ""
    units: str = ""
    default: str = ""               # raw default literal as written in source
    minimum: float | None = None
    maximum: float | None = None
    inferred_type: NmlType = NmlType.UNKNOWN
    enum_values: list[EnumValue] = field(default_factory=list)
    int_values: list[int] | None = None
    dimensions: list[str] | None = None
    nest_semantics: int = 0
    source: str = "source"          # "source" | "doc" | "both"
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        d = asdict(self)
        d["inferred_type"] = self.inferred_type.value
        d["enum_values"] = [e.to_dict() for e in self.enum_values]
        return d

    @classmethod
    def from_dict(cls, d: dict) -> "NmlOption":
        d = dict(d)
        d["inferred_type"] = NmlType(d.get("inferred_type", "unknown"))
        d["enum_values"] = [EnumValue.from_dict(e) for e in d.get("enum_values", [])]
        return cls(**d)


@dataclass
class Scheme:
    """A selectable physics scheme within a category (mp, pbl, ...)."""

    category: str           # "microphysics", "cumulus", ...
    selector: str           # owning namelist option, e.g. "mp"
    name: str               # "morrison"
    code: int | None        # 3
    constant: str | None    # "kMP_MORRISON"
    supported: bool = True
    description: str = ""

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "Scheme":
        return cls(**d)


@dataclass
class ModelVar:
    """A model state/output variable from the kVARS catalog."""

    kvar: str               # kVARS member, e.g. "u"
    name: str               # netCDF name, e.g. "u"
    standard_name: str = ""
    long_name: str = ""
    units: str = ""
    description: str = ""
    dimensions: str = ""    # symbolic dimension constant, e.g. "three_d_u_t_dimensions"
    minval: float | None = None
    maxval: float | None = None
    has_forcing_hook: bool = False
    forcing_option: str = ""  # opt%forcing%<x> var, when present

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "ModelVar":
        return cls(**d)


@dataclass
class Issue:
    """A validation finding."""

    severity: str           # "error" | "warning" | "info"
    group: str
    option: str
    message: str
    suggestion: str = ""

    def to_dict(self) -> dict:
        return asdict(self)
