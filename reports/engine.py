from typing import Any, Dict, List, Tuple, Optional
from collections import defaultdict
from django.apps import apps
from django.db.models import (
    Q, Count, Sum, Avg, Min, Max, F,
    DateField, DateTimeField, Field
)
from django.db.models.functions import (
    TruncDay, TruncWeek, TruncMonth, TruncQuarter, TruncYear
)
from .spec import ReportSpec, GroupSpec, MeasureSpec
from .filters import build_q
from . import registry
from crm.listview_views import tokenize, parse_expression, ast_to_q

GRAIN = {
    "day": TruncDay,
    "week": TruncWeek,
    "month": TruncMonth,
    "quarter": TruncQuarter,
    "year": TruncYear,
}
AGG = {
    "count": lambda field=None, distinct=False: Count(field or "id", distinct=distinct),
    "sum": Sum,
    "avg": Avg,
    "min": Min,
    "max": Max,
}


class ReportEngine:
    def _model(self, label: str):
        app, name = label.split(".")
        return apps.get_model(app, name)

    def _grain(self, g: GroupSpec) -> Tuple[str, Optional[Any]]:
        """
        Return (alias, expression_or_None).

        - Time grains: annotate with Trunc* and explicit output_field (best effort).
        - Related lookups (contains '__'): no annotation, just use raw path.
        - Plain fields: no annotation.
        """
        if getattr(g, "grain", None):
            base = g.field.replace("__", "_")
            fn = GRAIN.get(g.grain)

            if fn:
                # Best effort to detect field type for output_field
                Model = None
                try:
                    # GroupSpec may not have model; ignore if missing
                    Model = self._model(getattr(g, "model", "")) if getattr(g, "model", None) else None
                except Exception:
                    Model = None

                field: Optional[Field] = None
                if Model:
                    try:
                        parts = g.field.split("__")
                        field = Model._meta.get_field(parts[0])
                        for part in parts[1:]:
                            if hasattr(field, "related_model"):
                                Model = field.related_model
                                field = Model._meta.get_field(part)
                    except Exception:
                        field = None

                if isinstance(field, DateTimeField):
                    return f"{base}_{g.grain}", fn(g.field, output_field=DateTimeField())
                else:
                    # Default to date grain when unknown
                    return f"{base}_{g.grain}", fn(g.field, output_field=DateField())

            # Unknown grain → no annotation
            return g.field, None

        # Related lookup (e.g., user__username): use path directly
        if "__" in g.field:
            return g.field, None

        # Plain field
        return g.field, None

    def _measures(self, ms: List[MeasureSpec]) -> Tuple[Dict[str, Any], Dict[str, str]]:
        """
        Build aggregate expressions with safe SQL aliases and pretty labels.

        Returns:
            measures: Dict[alias, expression]
            titles:   Dict[alias, pretty_label]
        """
        measures: Dict[str, Any] = {}
        titles: Dict[str, str] = {}

        for m in ms or []:
            fn = (m.fn or "").lower()
            field = m.field or "id"

            # SQL-safe alias: fn_field (lowercase, no spaces)
            alias = f"{fn}_{field}".replace("__", "_").lower()
            pretty = f"{fn.upper()} {field}" if (field and fn != "count") else "Count"

            if fn == "count":
                measures[alias] = AGG["count"](m.field, distinct=getattr(m, "distinct", False))
                titles[alias] = pretty
                continue

            if fn in ("sum", "avg", "min", "max"):
                if not m.field:
                    raise ValueError(f"Measure '{fn}' requires a field (got None)")
                measures[alias] = AGG[fn](m.field)
                titles[alias] = pretty
                continue

            raise ValueError(f"Unsupported measure function: {fn}")

        if not measures:
            measures["count_id"] = Count("id")
            titles["count_id"] = "Count"

        return measures, titles


    def run(self, spec: ReportSpec, user=None) -> Dict[str, Any]:
        Model = self._model(spec.model)
        qs = Model._default_manager.all()
        qs = registry.apply_visibility(qs, user, spec.model)

       
        # FILTER LOGIC (AND / OR / NOT)
        filters = spec.filters or []
        filter_logic = getattr(spec, "filter_logic", "") or spec.__dict__.get("filter_logic", "")

        if filters:
            from crm.listview_views import tokenize, parse_expression, ast_to_q
            import re

            print("\n================ DEBUG START ================")
            print("RAW FILTERS:", filters)
            print("RAW LOGIC (DB):", filter_logic)

            qmap = {}


            # BUILD QMAP
            for i, r in enumerate(filters):
                data = r.__dict__ if hasattr(r, "__dict__") else r
                row_number = data.get("row_number") or (i + 1)

                q = build_q(Model, {
                    "field": data.get("field"),
                    "op": data.get("op"),
                    "value": data.get("value"),
                })

                print(f"\nFilter Row {row_number}:")
                print("DATA:", data)
                print("Q OBJECT:", q)

                if q is not None:
                    qmap[row_number] = q

            print("\nQMAP:", qmap)


            # NO VALID FILTERS
            if not qmap:
                print("NO VALID FILTERS → returning none()")
                qs = qs.none()
            else:
                valid_keys = set(qmap.keys())

    
                # 🔥 DO NOT MODIFY ORIGINAL
                original_logic = filter_logic
                logic_to_apply = filter_logic or ""

    
                # CLEAN INVALID NUMBERS
                if logic_to_apply:
                    def replace_invalid(m):
                        num = int(m.group(0))
                        return str(num) if num in valid_keys else ""

                    logic_to_apply = re.sub(r'\b\d+\b', replace_invalid, logic_to_apply)

    
                # NORMALIZE
                logic_to_apply = re.sub(r'\s+', ' ', logic_to_apply).strip().upper()

    
                # HANDLE "1 2 3"
                if logic_to_apply and re.fullmatch(r'[\d\s]+', logic_to_apply):
                    nums = re.findall(r'\d+', logic_to_apply)
                    logic_to_apply = " AND ".join(nums)

    
                # DEFAULT AND (RUNTIME ONLY)
                if (
                    not logic_to_apply or
                    logic_to_apply.endswith(("AND", "OR", "NOT")) or
                    logic_to_apply.startswith(("AND", "OR"))
                ):
                    logic_to_apply = " AND ".join(str(k) for k in sorted(valid_keys))

                print("\nORIGINAL LOGIC (UNCHANGED):", original_logic)
                print("LOGIC USED (RUNTIME):", logic_to_apply)

    
                # PARSE + BUILD Q
                try:
                    tokens = tokenize(logic_to_apply)
                    print("TOKENS:", tokens)

                    ast = parse_expression(tokens)
                    print("AST:", ast)

                    final_q = ast_to_q(ast, qmap)
                    print("FINAL Q:", final_q)

                except Exception as e:
                    print("PARSER ERROR:", str(e))
                    print("FALLBACK → DEFAULT AND")

                    final_q = None
                    for k in sorted(valid_keys):
                        if final_q is None:
                            final_q = qmap[k]
                        else:
                            final_q &= qmap[k]

    
                # APPLY FILTER
                if final_q is not None:
                    qs = qs.filter(final_q)
                    print("SQL:", str(qs.query))
                else:
                    qs = qs.none()

            print("================ DEBUG END ================\n")

        limit = max(1, min(int(spec.limit or 5000), 20000))

        # TABULAR
        if spec.view == "tabular":
            cols = spec.fields or registry.list_fields(spec.model)
            rows = list(qs.values(*cols)[:limit])
            return {"view": "tabular", "headers": cols, "rows": rows}

        # SUMMARY
        if spec.view == "summary":
            ra: List[str] = []
            rex: Dict[str, Any] = {}
            for g in spec.row_groups or []:
                a, e = self._grain(g)
                ra.append(a)
                if e is not None:
                    rex[a] = e
            if rex:
                qs = qs.annotate(**rex)

            measures, titles = self._measures(spec.measures)
            vqs = qs.values(*ra).annotate(**measures)

            if spec.sort and (spec.sort.by in measures or spec.sort.by in ra):
                vqs = vqs.order_by(
                    f"-{spec.sort.by}" if spec.sort.dir == "desc" else spec.sort.by
                )

            rows = list(vqs[:limit])

            # Accumulate with None-safety
            grand = {m: 0 for m in measures}
            subs = defaultdict(lambda: {m: 0 for m in measures})
            for r in rows:
                for m in measures:
                    v = r[m] if r[m] is not None else 0
                    grand[m] += v
                for i in range(len(ra)):
                    key = tuple((ga, r[ga]) for ga in ra[: i + 1])
                    for m in measures:
                        v = r[m] if r[m] is not None else 0
                        subs[key][m] += v

            return {
                "view": "summary",
                "rows": rows,
                "group_keys": ra,
                # Keep aliases here to match dict keys in rows/cell lookups (template compatibility)
                "measure_labels": list(measures.keys()),
                "grand_total": grand,
                "subtotals": {str(k): v for k, v in subs.items()},
                # Optional pretty titles if you want to use later
                "measure_titles": titles,
            }

        # MATRIX
        if spec.view == "matrix":
            ra: List[str] = []
            rex: Dict[str, Any] = {}
            ca: List[str] = []
            cex: Dict[str, Any] = {}

            for g in spec.row_groups or []:
                a, e = self._grain(g)
                ra.append(a)
                if e is not None:
                    rex[a] = e
            for g in spec.col_groups or []:
                a, e = self._grain(g)
                ca.append(a)
                if e is not None:
                    cex[a] = e

            if rex:
                qs = qs.annotate(**rex)
            if cex:
                qs = qs.annotate(**cex)

            measures, titles = self._measures(spec.measures)
            vqs = qs.values(*ra, *ca).annotate(**measures)
            raw = list(vqs[:limit])

            def uniq(seq):
                seen = set()
                out = []
                for x in seq:
                    if x not in seen:
                        seen.add(x)
                        out.append(x)
                return out

            rows = uniq([tuple((a, r[a]) for a in ra) for r in raw]) if ra else [tuple()]
            cols = uniq([tuple((a, r[a]) for a in ca) for r in raw]) if ca else [tuple()]

            from collections import defaultdict as _dd
            cell = _dd(lambda: {m: 0 for m in measures})
            rtot = _dd(lambda: {m: 0 for m in measures})
            ctot = _dd(lambda: {m: 0 for m in measures})
            grand = {m: 0 for m in measures}

            # NEW: nested map for reliable template lookups: {str(rk)}->{str(ck)}->{measure_alias: value}
            cell_nested = _dd(lambda: _dd(lambda: {m: 0 for m in measures}))

            for r in raw:
                rk = tuple((a, r[a]) for a in ra) if ra else tuple()
                ck = tuple((a, r[a]) for a in ca) if ca else tuple()

                rks = str(rk)  # string keys used by template
                cks = str(ck)

                for m in measures:
                    v = r[m] if r[m] is not None else 0  # None-safe
                    cell[(rk, ck)][m] += v
                    rtot[rk][m] += v
                    ctot[ck][m] += v
                    grand[m] += v

                    # fill nested structure
                    cell_nested[rks][cks][m] += v

            if spec.sort and spec.sort.by in measures:
                rows.sort(
                    key=lambda rk: rtot[rk][spec.sort.by],
                    reverse=(spec.sort.dir == "desc"),
                )

            return {
                "view": "matrix",
                "row_headers": ra,
                "col_headers": ca,
                "rows": rows,
                "cols": cols,
                "cell": {f"{rk}|{ck}": vals for (rk, ck), vals in cell.items()},
                "cell_nested": {rk: dict(inner) for rk, inner in cell_nested.items()},  # <<<
                "row_totals": {str(rk): v for rk, v in rtot.items()},
                "col_totals": {str(ck): v for ck, v in ctot.items()},
                "grand_total": grand,
                # Keep aliases here to match template lookups
                "measure_labels": list(measures.keys()),
                # Optional pretty titles
                "measure_titles": titles,
            }

        # DEFAULT
        data = list(qs.values()[:limit])
        return {
            "view": "tabular",
            "headers": list(data[0].keys()) if data else [],
            "rows": data,
        }
