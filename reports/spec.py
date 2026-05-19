from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional, Literal

ViewType = Literal["tabular","summary","matrix"]

@dataclass
class GroupSpec:
    field: str
    grain: Optional[Literal["day","week","month","quarter","year"]] = None

@dataclass
class MeasureSpec:
    fn: Literal["count","sum","avg","min","max"] = "count"
    field: Optional[str] = None
    label: Optional[str] = None
    distinct: bool = False

@dataclass
class FilterSpec:
    field: str
    op: Literal["eq","neq","lt","lte","gt","gte","in","not_in","contains","not_contains","startswith","endswith","isnull","range"] = "eq"
    value: Any = None

@dataclass
class SortSpec:
    by: str
    dir: Literal["asc","desc"] = "desc"

@dataclass
class ReportSpec:
    model: str
    view: ViewType = "summary"
    limit: int = 5000
    fields: List[str] = field(default_factory=list)
    row_groups: List[GroupSpec] = field(default_factory=list)
    col_groups: List[GroupSpec] = field(default_factory=list)
    measures: List[MeasureSpec] = field(default_factory=lambda: [MeasureSpec(fn="count", label="Count")])
    filters: List[FilterSpec] = field(default_factory=list)
    sort: Optional[SortSpec] = None
    filter_logic: str = ""
    def to_dict(self) -> Dict[str,Any]: return asdict(self)
    @staticmethod
    def from_dict(data: Dict[str,Any]) -> "ReportSpec":
        def mk(cls, d):
            if not isinstance(d, dict):
                return d

            # Allowed fields per class
            allowed = {
                GroupSpec: {"field", "grain"},
                MeasureSpec: {"fn", "field", "label", "distinct"},
                FilterSpec: {"field", "op", "value"},   # 🔥 id excluded
                SortSpec: {"by", "dir"},
            }

            clean = {k: v for k, v in d.items() if k in allowed.get(cls, {})}
            return cls(**clean)
        return ReportSpec(
            model=data["model"], view=data.get("view","summary"), limit=int(data.get("limit",5000)),
            fields=list(data.get("fields",[])),
            row_groups=[mk(GroupSpec, g) for g in data.get("row_groups",[])],
            col_groups=[mk(GroupSpec, g) for g in data.get("col_groups",[])],
            measures=[mk(MeasureSpec, m) for m in data.get("measures",[])],
            filters=[mk(FilterSpec, f) for f in data.get("filters",[])],
            sort=mk(SortSpec, data.get("sort")) if data.get("sort") else None,
            filter_logic=data.get("filter_logic", "")
        )
