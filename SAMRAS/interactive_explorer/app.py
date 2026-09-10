"""Local, read-only SAMRASS exploration. Run with python -m streamlit run app.py."""
from __future__ import annotations

import sys
sys.dont_write_bytecode = True

import copy
import json
from html import escape
from pathlib import Path
import uuid

import numpy as np
import pandas as pd
import plotly.express as px
import streamlit as st

APP_DIR = Path(__file__).resolve().parent
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

import analysis as an
import charts
import theme

st.set_page_config(page_title="SAMRASS | Accident explorer", page_icon="◈", layout="wide")

COMMODITIES = {
    "AU": "Gold", "PT": "Platinum group metals", "CL": "Coal", "CR": "Chrome",
    "DI": "Diamonds", "FE": "Iron ore", "MN": "Manganese", "CU": "Copper",
    "NI": "Nickel", "UR": "Uranium", "LS": "Limestone", "DM": "Dolomite",
}
MODES = {
    "total": "Count / total", "share": "Share of comparison (%)",
    "outcome_pct": "Outcome percentage", "fatalities_per_1000": "Fatalities per 1,000 records",
}
REFERENCE = "Reference population"
ALL = "All SAMRASS"
RESERVED_NAMES = {REFERENCE, ALL, "__draft__", "Create a new group", "Parent group",
                  "Remainder of parent", "Selected group (composition)"}
DIMENSIONS = [
    "hazard_mechanism", "location_text", "location_group", "commodity", "cause_text",
    "mining_method_group", "severity_group", "evidence_tier", "region", "occupation_text",
    "task_text", "activity_text", "drilling_context", "body_part_injured", "gender",
]
OPS = {"in": "is any of", "not_in": "is none of", "between": "is between",
       "gte": "is at least", "lte": "is at most", "contains": "contains text",
       "not_contains": "does not contain", "is_missing": "is missing", "not_missing": "is recorded"}


@st.cache_data(show_spinner=False, persist=None, max_entries=2)
def cached_data(path: str, signature: tuple[int, int]) -> pd.DataFrame:
    return an.load_data(Path(path))


def number(value: float, decimals: int = 0) -> str:
    if value is None or not np.isfinite(float(value)):
        return "—"
    return f"{value:,.{decimals}f}"


def field_label(field: str) -> str:
    return an.FIELD_LABELS.get(field, field.replace("_", " ").capitalize())


def commodity_label(value: str) -> str:
    return f"{COMMODITIES[value]} ({value})" if value in COMMODITIES else str(value)


def fresh_rules(rules: list[dict]) -> list[dict]:
    return [dict(copy.deepcopy(rule), _id=uuid.uuid4().hex[:10]) for rule in rules]


def rule_editor(data: pd.DataFrame, prefix: str) -> list[dict]:
    """Edit safe predicates; arbitrary Python or regular expressions are never evaluated."""
    storage = f"{prefix}_rows"
    st.session_state.setdefault(storage, [])
    rules = []
    fields = [f for f in an.FIELD_LABELS if f in data.columns]
    for row in list(st.session_state[storage]):
        ident = f"{prefix}_{row['_id']}"
        col1, col2, col3, col4 = st.columns([2.1, 1.5, 3, 0.45], vertical_alignment="bottom")
        start_field = row.get("field", "location_group")
        with col1:
            field = st.selectbox("Field", fields, index=fields.index(start_field) if start_field in fields else 0,
                                 format_func=field_label, key=f"{ident}_field")
        numeric = field in an.NUMERIC_FIELDS
        text_only = field in {"accident_description", "record_id", "working_place", "section", "evidence_snippet"}
        ops = (["between", "gte", "lte", "is_missing", "not_missing"] if numeric else
               ["contains", "not_contains", "is_missing", "not_missing"] if text_only else
               ["in", "not_in", "contains", "not_contains", "is_missing", "not_missing"])
        initial_op = row.get("op", ops[0])
        with col2:
            op = st.selectbox("Condition", ops, index=ops.index(initial_op) if initial_op in ops else 0,
                              format_func=OPS.get, key=f"{ident}_{field}_op")
        initial = row.get("value") if field == start_field and op == initial_op else None
        value_key = f"{ident}_{field}_{op}_value"
        with col3:
            if op in {"in", "not_in"}:
                options = sorted(an.category_series(data, field).unique().tolist(), key=str)
                defaults = [v for v in (initial or []) if v in options]
                value = st.multiselect("Values", options, default=defaults, key=value_key,
                                       format_func=commodity_label if field == "commodity" else str)
            elif op in {"contains", "not_contains"}:
                value = st.text_input("Text (case insensitive)", value=str(initial or ""), key=value_key)
            elif op in {"between", "gte", "lte"}:
                finite = pd.to_numeric(data[field], errors="coerce").replace([np.inf, -np.inf], np.nan).dropna()
                low = float(finite.min()) if len(finite) else 0.0
                high = float(finite.max()) if len(finite) else 1.0
                if op == "between":
                    bounds = initial if isinstance(initial, (list, tuple)) and len(initial) == 2 else [low, high]
                    left, right = st.columns(2)
                    with left:
                        lo = st.number_input("From", value=float(bounds[0]), key=value_key + "_lo")
                    with right:
                        hi = st.number_input("To", value=float(bounds[1]), key=value_key + "_hi")
                    value = [lo, hi]
                else:
                    value = st.number_input("Value", value=float(initial) if initial is not None else low,
                                            key=value_key)
            else:
                st.caption("Blank or unavailable values" if op == "is_missing" else "Values present in the saved data")
                value = None
        with col4:
            if st.button("×", key=ident + "_remove", help="Remove condition"):
                st.session_state[storage] = [r for r in st.session_state[storage] if r["_id"] != row["_id"]]
                st.rerun()
        rules.append({"field": field, "op": op, "value": value})
    if st.button("Add condition", key=prefix + "_add"):
        # Keep current edits when adding a new row.
        st.session_state[storage] = [dict(r, _id=old["_id"]) for r, old in zip(rules, st.session_state[storage])]
        st.session_state[storage].append({"_id": uuid.uuid4().hex[:10], "field": "location_group", "op": "in", "value": []})
        st.rerun()
    return rules


def clear_drill() -> None:
    st.session_state.drill = []
    st.session_state.view_version = st.session_state.get("view_version", 0) + 1


def reset_reference() -> None:
    for key in ["reference_years", "reference_commodities", "reference_locations", "reference_logic"]:
        st.session_state.pop(key, None)
    st.session_state.reference_extra_rows = []
    clear_drill()


def add_drill(description: str, alternatives: list[list[dict]]) -> None:
    item = {"description": description, "alternatives": alternatives}
    if item not in st.session_state.drill:
        st.session_state.drill.append(item)
        st.session_state.view_version += 1
        st.rerun()


def apply_drill(data: pd.DataFrame, group_mask: pd.Series) -> pd.Series:
    result = group_mask.copy()
    for selection in st.session_state.drill:
        choice = pd.Series(False, index=data.index)
        for clause in selection["alternatives"]:
            choice |= an.apply_rules(data, clause, "AND")
        result &= choice
    return result


def handle_selection(event, fields: list[str], name: str) -> None:
    if not event:
        return
    points = event.get("selection", {}).get("points", [])
    alternatives = []
    for point in points:
        values = point.get("customdata", [])
        if not isinstance(values, (list, tuple)) or len(values) < len(fields):
            continue
        rules = [{"field": field, "op": "in", "value": [values[i]]} for i, field in enumerate(fields)]
        if rules not in alternatives:
            alternatives.append(rules)
    if alternatives:
        labels = [" / ".join(str(rule["value"][0]) for rule in rules) for rules in alternatives]
        add_drill(f"{name}: " + "; ".join(labels), alternatives)


def metric_label(mode: str, measure: str, outcome_label: str) -> str:
    if mode == "total":
        return an.MEASURES[measure]
    if mode == "share":
        return f"{an.MEASURES[measure]} (% of comparison)"
    if mode == "outcome_pct":
        return f"{outcome_label} (%)"
    return "Fatalities per 1,000 records"


def comparison_mask(data, focus_name, groups, reference_mask, target):
    if focus_name == REFERENCE:
        parent_name, parent = ALL, pd.Series(True, index=data.index)
    else:
        parent_name = groups[focus_name]["parent"]
        parent = an.resolve_group_mask(data, parent_name, groups, reference_mask)
    if target == "Parent group":
        return parent_name, parent
    if target == "Remainder of parent":
        selected = an.resolve_group_mask(data, focus_name, groups, reference_mask)
        return f"{parent_name} minus {focus_name}", parent & ~selected
    if target == "Selected group (composition)":
        return focus_name, an.resolve_group_mask(data, focus_name, groups, reference_mask)
    return target, an.resolve_group_mask(data, target, groups, reference_mask)


def show_comparison(data, view, other, view_name, other_name, mode, measure, outcome):
    rows = []
    for name, mask in [(view_name, view), (other_name, other)]:
        metric = an.calculate_metric(data, mask, measure, mode, outcome, other)
        row = {"Population": name, "Records": int(mask.sum()),
               "Injured persons": an.measure_total(data[mask], "injured"),
               "Fatalities": an.measure_total(data[mask], "fatalities"),
               "Disabled persons": an.measure_total(data[mask], "disabled"),
               "Metric value": metric["value"], "Numerator": metric["numerator"],
               "Denominator": metric["denominator"]}
        rows.append(row)
    st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch")
    overlap = int((view & other).sum())
    st.caption(f"Shared records: {overlap:,}. Populations with shared records must not be added as separate accidents.")


def groups_panel(data, groups, reference_mask, focus_name):
    st.subheader("Create and refine groups")
    st.caption("Groups are evaluated inside their parent. Different named groups may overlap. Changes last for this browser session.")
    target = st.selectbox("Group to edit", ["Create a new group"] + list(groups), key="editor_target")
    draft_signature = (target, st.session_state.get("editor_revision", 0))
    if st.session_state.get("draft_signature") != draft_signature:
        definition = groups.get(target, {"parent": focus_name, "logic": "AND", "rules": []})
        st.session_state["groupdraft_rows"] = fresh_rules(definition["rules"])
        st.session_state["draft_name"] = "" if target == "Create a new group" else target
        st.session_state["draft_parent"] = definition["parent"]
        st.session_state["draft_logic"] = definition["logic"]
        st.session_state.draft_signature = draft_signature
    c1, c2, c3 = st.columns([2, 2, 1.2])
    with c1:
        name = st.text_input("Group name", key="draft_name", disabled=target != "Create a new group")
    with c2:
        parents = [REFERENCE] + [n for n in groups if n != target]
        if st.session_state.get("draft_parent") not in parents:
            st.session_state.draft_parent = REFERENCE
        parent = st.selectbox("Parent population", parents, key="draft_parent")
    with c3:
        logic = st.radio("Match conditions", ["AND", "OR"], horizontal=True, key="draft_logic")
    rules = rule_editor(data, "groupdraft")
    definition = {"parent": parent, "logic": logic, "rules": rules}
    try:
        draft_groups = dict(groups, **{"__draft__": definition})
        preview = an.resolve_group_mask(data, "__draft__", draft_groups, reference_mask)
        st.caption(f"Preview: {int(preview.sum()):,} records; {number(an.measure_total(data[preview], 'injured'))} injured persons. Empty condition lists include the whole parent.")
    except (ValueError, KeyError, TypeError) as exc:
        st.warning(str(exc))
    save, delete = st.columns([1, 1])
    with save:
        if st.button("Save group in this session", type="primary"):
            clean_name = name.strip()
            if not clean_name or clean_name in RESERVED_NAMES:
                st.error("Choose a group name distinct from the reference and whole dataset.")
            elif target == "Create a new group" and clean_name in groups:
                st.error("That name already exists. Select it above to edit its conditions.")
            else:
                proposed = copy.deepcopy(groups)
                proposed[clean_name] = definition
                try:
                    # Validate every group, including descendants after an edit.
                    for group in proposed:
                        an.resolve_group_mask(data, group, proposed, reference_mask)
                except (ValueError, KeyError, TypeError) as exc:
                    st.error(str(exc))
                else:
                    st.session_state.groups = proposed
                    st.session_state.pending_active = clean_name
                    st.session_state.editor_revision = st.session_state.get("editor_revision", 0) + 1
                    clear_drill()
                    st.rerun()
    with delete:
        children = [n for n, spec in groups.items() if spec["parent"] == target]
        if target in groups and st.button("Delete this session group", disabled=bool(children), help="Groups with child groups cannot be deleted."):
            del st.session_state.groups[target]
            st.session_state.pending_active = REFERENCE
            st.session_state.pop("editor_target", None)
            st.session_state.editor_revision = st.session_state.get("editor_revision", 0) + 1
            clear_drill()
            st.rerun()
    with st.expander("Current group definitions"):
        st.json(groups, expanded=False)


def records_panel(data, view):
    st.subheader("Records behind the figures")
    st.caption("Select rows to inspect their complete narratives, or use them to narrow the current view.")
    candidates = data[view].sort_values(["year", "record_id"], kind="stable")
    c1, c2, c3 = st.columns([3, 1, 1])
    with c1:
        search = st.text_input("Find a record ID or narrative text", key="record_search")
    if search:
        candidates = candidates[candidates.record_id.astype(str).str.contains(search, case=False, regex=False) |
                                candidates.accident_description.astype(str).str.contains(search, case=False, regex=False)]
    with c2:
        size = st.selectbox("Rows per page", [50, 100, 250], key="record_page_size")
    pages = max(1, (len(candidates) + size - 1) // size)
    page_key = f"record_page_{st.session_state.view_version}_{size}_{search}"
    with c3:
        page = st.number_input("Page", min_value=1, max_value=pages, value=1, key=page_key)
    page_data = candidates.iloc[(page - 1) * size:page * size].reset_index(drop=True)
    cols = ["record_id", "year", "commodity", "persons_injured", "persons_killed", "persons_disabled",
            "location_text", "hazard_mechanism", "evidence_tier", "cause_text"]
    cols = [c for c in cols if c in data]
    st.caption(f"{len(candidates):,} matching records · page {page:,} of {pages:,}. This search affects the record list; use the selection button to filter the charts.")
    selection = st.dataframe(page_data[cols], hide_index=True, width="stretch", height=390, row_height=38,
                             column_config={
                                 "record_id": st.column_config.TextColumn("Record ID", width="medium"),
                                 "year": st.column_config.NumberColumn("Year", format="%d", width="small"),
                                 "commodity": st.column_config.TextColumn("Commodity", width="small"),
                                 "persons_injured": st.column_config.NumberColumn("Injured", format="%d", width="small"),
                                 "persons_killed": st.column_config.NumberColumn("Killed", format="%d", width="small"),
                                 "persons_disabled": st.column_config.NumberColumn("Disabled", format="%d", width="small"),
                                 "location_text": "Location", "hazard_mechanism": "Mechanism",
                                 "evidence_tier": "Illumination tier", "cause_text": "Recorded cause",
                             },
                             selection_mode="multi-row", on_select="rerun",
                             key=f"records_{st.session_state.view_version}_{page}_{size}_{search}")
    chosen = selection.get("selection", {}).get("rows", [])
    chosen = [int(i) for i in chosen if 0 <= int(i) < len(page_data)]
    if chosen:
        selected = page_data.iloc[chosen]
        if st.button(f"Filter view to these {len(selected):,} selected records"):
            add_drill("Selected records", [[{"field": "record_id", "op": "in", "value": selected.record_id.tolist()}]])
        identity = st.selectbox("Read selected record", selected.record_id.tolist(), key=f"detail_{st.session_state.view_version}_{page}")
        record = selected[selected.record_id.eq(identity)].iloc[0]
    elif len(page_data):
        st.caption("Showing the first listed record until you select a row.")
        record = page_data.iloc[0]
    else:
        st.info("No records match this view and search.")
        return
    with st.container(border=True, key="narrative_panel"):
        st.markdown(f"**Record {record.record_id}**")
        st.text(str(record.accident_description) if str(record.accident_description).strip() else "No narrative supplied.")
    detail_fields = ["source_file", "source_year", "regional_accident_no", "mine_accident_no", "date_of_accident",
                     "location_text", "location_group", "working_place", "commodity", "task_text", "activity_text",
                     "drilling_context", "cause_text", "hazard_mechanism", "evidence_tier", "evidence_search_scope",
                     "matched_phrase", "evidence_snippet", "persons_injured", "persons_killed", "persons_disabled"]
    with st.expander("Source fields and evidence", expanded=False):
        st.dataframe(pd.DataFrame([{"Field": field_label(f), "Value": str(record[f])} for f in detail_fields if f in record]),
                     hide_index=True, width="stretch")


def coverage_and_workforce(data, view, years):
    coverage_tab, workforce_tab = st.tabs(["Field coverage", "Commodity workforce rates"])
    with coverage_tab:
        st.caption("Missing values remain visible. Activities and tasks chiefly cover 2010 and 2024; a missing activity does not mean it did not occur.")
        fields = [f for f in an.FIELD_LABELS if f in data]
        report = an.coverage(data, view, fields).copy()
        report["field"] = report["field"].map(field_label)
        st.dataframe(report, hide_index=True, width="stretch", height=450)
        st.caption("Year uses the saved analysis year. The incomplete parsed-date field is not used for filtering. Source cause categories, inferred mechanisms, and illumination tiers retain separate meanings.")
        st.caption("Drilling presets distinguish recorded activities from explicit narrative evidence. Equipment handling and ambiguous mentions are not counted as active drilling. They do not establish that illumination was inadequate.")
    with workforce_tab:
        st.subheader("Full commodity populations")
        st.info("This is a separate commodity/year comparison. Group, location, age, and drilling filters do not define workforce exposure. The controls below select complete commodity populations from the whole dataset.")
        c1, c2, c3 = st.columns([2, 2, 1.5])
        with c1:
            commodities = st.multiselect("Complete commodity populations", list(an.WORKFORCE_COMMODITIES),
                                         default=["AU", "PT", "CL"], format_func=commodity_label, key="workforce_commodities")
        with c2:
            period = st.slider("Workforce comparison years", min_value=2005, max_value=2024,
                               value=(2005, 2024), key="workforce_years")
        with c3:
            measure = st.selectbox("Workforce numerator", ["records", "injured", "fatalities", "disabled"],
                                   format_func=an.MEASURES.get, key="workforce_measure")
        if not commodities:
            st.info("Select at least one commodity.")
            return
        try:
            selected_years = list(range(period[0], period[1] + 1))
            annual = an.workforce_rates(data, selected_years, commodities, measure)
            pooled = an.workforce_rates(data, selected_years, commodities, measure, pooled=True)
        except (ValueError, OSError, KeyError) as exc:
            st.error(f"Workforce comparison unavailable: {exc}")
            return
        fig = px.line(annual, x="year", y="value", color="commodity", markers=True,
                      custom_data=["numerator", "denominator"],
                      labels={"year": "Year", "value": f"{an.MEASURES[measure]} per 1,000 employees", "commodity": "Commodity"},
                      color_discrete_sequence=theme.CATEGORICAL)
        theme.style_figure(fig, height=380)
        fig.update_layout(margin=dict(l=10, r=20, t=20, b=10))
        fig.update_traces(hovertemplate="Year %{x}<br>Rate %{y:.3f}<br>Numerator %{customdata[0]:,}<br>Employees %{customdata[1]:,}<extra>%{fullData.name}</extra>")
        st.plotly_chart(fig, width="stretch", theme=None, config={"displaylogo": False, "modeBarButtonsToRemove": ["toImage"]})
        st.caption("Annual rates use the matched annual employee count. Pooled rates divide summed outcomes by summed annual employment, an employee-years proxy. Zero-accident years retain their employment denominator.")
        st.dataframe(pooled, hide_index=True, width="stretch")
        with st.expander("Annual numerators and denominators"):
            st.dataframe(annual, hide_index=True, width="stretch")


def main():
    st.markdown(theme.CSS, unsafe_allow_html=True)
    try:
        info = an.INPUT_CSV.stat()
        data = cached_data(str(an.INPUT_CSV), (info.st_mtime_ns, info.st_size))
    except (OSError, ValueError, KeyError) as exc:
        st.error(f"Cannot load the saved SAMRASS master: {exc}")
        st.stop()
    st.session_state.setdefault("groups", an.preset_groups())
    st.session_state.setdefault("drill", [])
    st.session_state.setdefault("view_version", 0)
    groups = st.session_state.groups
    if "pending_active" in st.session_state:
        st.session_state.active_group = st.session_state.pop("pending_active")
    if st.session_state.get("active_group") not in [REFERENCE] + list(groups):
        st.session_state.active_group = next(iter(groups), REFERENCE)

    with st.sidebar:
        st.markdown('<div class="sidebar-brand"><div class="brand-mark">◈</div><div><div class="brand-name">SAMRASS</div><div class="brand-sub">Accident data explorer</div></div></div>', unsafe_allow_html=True)
        st.markdown('<div class="sidebar-section"><span>01</span>Reference population</div>', unsafe_allow_html=True)
        first, last = int(data.year.min()), int(data.year.max())
        years = st.slider("Analysis years", first, last, (first, last), key="reference_years")
        commodity_options = sorted(an.category_series(data, "commodity").unique().tolist())
        commodities = st.multiselect("Commodities", commodity_options, format_func=commodity_label, placeholder="All commodities", key="reference_commodities")
        locations = st.multiselect("Broad locations", sorted(an.category_series(data, "location_group").unique().tolist()), placeholder="All locations", key="reference_locations")
        basic = [{"field": "year", "op": "between", "value": list(years)}]
        if commodities:
            basic.append({"field": "commodity", "op": "in", "value": commodities})
        if locations:
            basic.append({"field": "location_group", "op": "in", "value": locations})
        st.caption("Empty filters include all categories and missing values.")
        st.button("Reset reference filters", on_click=reset_reference, width="stretch")
        st.divider()
        st.markdown('<div class="sidebar-section"><span>02</span>Explore a group</div>', unsafe_allow_html=True)
        focus_name = st.selectbox("Explore a group", [REFERENCE] + list(groups), key="active_group", label_visibility="collapsed")
        st.caption("Build and edit groups in the Groups tab.")
        with st.expander("Session"):
            st.caption("Groups and filters last for this session. No automatic exports.")
            if st.button("Reload source data", width="stretch"):
                cached_data.clear()
                clear_drill()
                st.rerun()

    heading, filters = st.columns([3, 1.2], vertical_alignment="center")
    with heading:
        st.markdown('<div class="app-heading"><div class="eyebrow">SOUTH AFRICAN MINING · 2005–2024</div><h1>Accident explorer</h1><p>Compare populations and inspect the evidence behind each pattern.</p></div>', unsafe_allow_html=True)
    with filters:
        with st.popover("More filters", icon=":material/tune:", help="Additional conditions for the reference population", width="stretch"):
            st.subheader("Additional reference conditions")
            st.caption("These conditions apply to the reference population and all of its groups.")
            ref_logic = st.radio("Match additional reference conditions", ["AND", "OR"], horizontal=True, key="reference_logic")
            ref_rules = rule_editor(data, "reference_extra")
    try:
        reference_mask = an.apply_rules(data, basic, "AND") & an.apply_rules(data, ref_rules, ref_logic)
        group_mask = an.resolve_group_mask(data, focus_name, groups, reference_mask)
    except (ValueError, KeyError, TypeError) as exc:
        st.error(f"Check the filter conditions: {exc}")
        st.stop()
    context = json.dumps([basic, ref_rules, ref_logic, focus_name, groups, info.st_mtime_ns], sort_keys=True)
    if st.session_state.get("context") != context:
        clear_drill()
        st.session_state.context = context
    view = apply_drill(data, group_mask)
    with st.container(key="population_summary"):
        cards = st.columns(4)
        for card, label, count in zip(cards, ["Whole dataset", "Reference population", "Selected group", "Current view"],
                                      [len(data), reference_mask.sum(), group_mask.sum(), view.sum()]):
            card.metric(label, number(count))
    st.markdown(f'<div class="scope-line"><span class="scope-name">{escape(focus_name)}</span><span class="scope-period">{years[0]}–{years[1]} reference period</span></div>', unsafe_allow_html=True)
    if st.session_state.drill:
        st.caption("Drilldown: " + " → ".join(item["description"] for item in st.session_state.drill))
        b1, b2, _ = st.columns([1, 1, 4])
        with b1:
            if st.button("Back one step"):
                st.session_state.drill.pop()
                st.session_state.view_version += 1
                st.rerun()
        with b2:
            st.button("Clear drilldown", on_click=clear_drill)

    explore, group_tab, records, context_tab = st.tabs(["Explore", "Groups", "Records", "Coverage & workforce"])
    with explore:
        with st.container(border=True, key="measure_controls"):
            c1, c2, c3, readout = st.columns([1.35, 1.35, 1.8, 1.05])
            with c1:
                mode = st.selectbox("Display", list(MODES), format_func=MODES.get, key="metric_mode")
            measure, outcome, outcome_label = "records", "fatal", an.OUTCOMES["fatal"]
            with c2:
                if mode in {"total", "share"}:
                    if "measure" not in st.session_state:
                        st.session_state.measure = "injured"
                    measure = st.selectbox("Measure", list(an.MEASURES), format_func=an.MEASURES.get, key="measure")
                elif mode == "outcome_pct":
                    choices = list(an.OUTCOMES) + [f"group:{g}" for g in groups]
                    if st.session_state.get("outcome", "fatal") not in choices:
                        st.session_state.outcome = "fatal"
                    choice = st.selectbox("Numerator outcome", choices,
                                          format_func=lambda v: an.OUTCOMES.get(v, "In group: " + v.removeprefix("group:")),
                                          index=choices.index("fatal"), key="outcome")
                    if choice.startswith("group:"):
                        outcome_label = "Membership in " + choice[6:]
                        outcome = an.resolve_group_mask(data, choice[6:], groups, reference_mask)
                    else:
                        outcome, outcome_label = choice, an.OUTCOMES[choice]
                else:
                    st.caption("Persons killed ÷ accident records × 1,000")
            with c3:
                targets = ["Parent group", "Reference population", ALL, "Remainder of parent", "Selected group (composition)"] + [n for n in groups if n != focus_name]
                if st.session_state.get("comparison") not in targets:
                    st.session_state.comparison = "Parent group"
                target = st.selectbox("Compare with / share denominator", targets, key="comparison")
            other_name, other = comparison_mask(data, focus_name, groups, reference_mask, target)
            result = an.calculate_metric(data, view, measure, mode, outcome, other)
            label = metric_label(mode, measure, outcome_label)
            value = number(result["value"], 2 if mode != "total" else 0)
            with readout:
                st.markdown(f'<div class="measure-readout"><div class="measure-label">{escape(label)}</div><div class="measure-value">{value}</div></div>', unsafe_allow_html=True)
            if mode == "share":
                st.caption(f"Numerator: {number(result['numerator'])} {an.MEASURES[measure].lower()} in the current view. Denominator: {number(result['denominator'])} in {other_name}. A comparison with an overlapping or smaller group is a ratio and may exceed 100%.")
            elif mode == "outcome_pct":
                st.caption(f"Numerator: {number(result['numerator'])} records matching {outcome_label.lower()}. Denominator: all {number(result['denominator'])} records in the current view. Outcome choice does not filter that denominator.")
            elif mode == "fatalities_per_1000":
                st.caption(f"Numerator: {number(result['numerator'])} persons killed. Denominator: {number(result['denominator'])} accident records in the current view. This describes recorded accident severity, not worker exposure risk.")
            else:
                st.caption("Record counts and person totals are different units. Injured, killed, and totally disabled persons are reported separately.")
            if mode != "total" and not np.isfinite(float(result["value"])):
                st.info("This measure is undefined because its denominator is zero.")
        if not view.any():
            st.info("No records match this view. Adjust the group/reference conditions or clear the drilldown.")
            with st.expander("Population comparison", expanded=False):
                show_comparison(data, view, other, "Current view: " + focus_name, other_name, mode, measure, outcome)
        else:
            choices = [f for f in DIMENSIONS if f in data]
            left, right, tool = st.columns([2.2, 1, 1.3])
            with left:
                dimension = st.selectbox("Break down by", choices, format_func=field_label, key="bar_dimension")
            with right:
                top_n = st.slider("Categories to display", 5, 30, 12, key="top_n")
            with tool:
                gesture = st.selectbox("Selection tool", ["Click a category", "Drag a selection box"], key="selection_tool")
            selection_mode = "points" if gesture == "Click a category" else "box"
            table = an.summarize_by(data, view, [dimension], measure, mode, outcome, other)
            st.caption("Click a category or year to narrow the view. Choose box selection to include several; the reference stays fixed.")
            with st.container(key="chart_grid"):
                ranked, timeline = st.columns([1.15, 1], gap="medium")
                with ranked:
                    with st.container(border=True, key="ranked_panel"):
                        st.subheader("Ranked categories")
                        st.caption(f"{min(top_n, len(table))} of {len(table):,} categories · {field_label(dimension)}")
                        fig = charts.bar_figure(table, dimension, field_label(dimension), label, top_n)
                        fig.update_layout(clickmode="event+select",
                                          dragmode="pan" if selection_mode == "points" else "select")
                        event = st.plotly_chart(fig, width="stretch", theme=None, on_select="rerun", selection_mode=selection_mode,
                                                key=f"bar_{st.session_state.view_version}_{dimension}_{mode}_{measure}_{selection_mode}",
                                                config={"displaylogo": False, "modeBarButtonsToRemove": ["toImage"]})
                        handle_selection(event, [dimension], field_label(dimension))
                        with st.expander("All category values and denominators"):
                            st.dataframe(table, hide_index=True, width="stretch")
                with timeline:
                    with st.container(border=True, key="trend_panel"):
                        st.subheader("Change over time")
                        trend_mode = st.radio("Time series", ["Total", "Displayed categories"],
                                              horizontal=True, key="trend_mode", label_visibility="collapsed")
                        series_field = dimension if trend_mode == "Displayed categories" else None
                        categories = charts.ranked_categories(table, dimension, top_n)[dimension].tolist() if series_field else None
                        annual = an.summarize_annual(data, view, years, measure, mode, outcome, other, series_field, categories)
                        if series_field:
                            st.caption(f"{len(categories)} series. Same categories as the ranked bars. Click a point for its category and year; use the legend to hide or isolate lines.")
                        else:
                            st.caption(f"{years[0]}-{years[1]}. Total for the current view, including categories beyond the ranked bars. Click a year to inspect its records.")
                        trend = charts.trend_figure(annual, label, series_field, field_label(dimension))
                        trend.update_layout(height=max(fig.layout.height, trend.layout.height), clickmode="event+select",
                                            dragmode="pan" if selection_mode == "points" else "select")
                        event = st.plotly_chart(trend, width="stretch", theme=None, on_select="rerun", selection_mode=selection_mode,
                                                key=f"trend_{st.session_state.view_version}_{mode}_{measure}_{selection_mode}_{dimension}_{trend_mode}_{top_n}",
                                                config={"displaylogo": False, "modeBarButtonsToRemove": ["toImage"]})
                        handle_selection(event, ["year"] + ([dimension] if series_field else []),
                                         f"Year / {field_label(dimension)}" if series_field else "Year")
                        with st.expander("Annual values and denominators"):
                            if mode == "share":
                                st.caption(f"Each point uses the same full-period denominator: {number(result['denominator'])} {an.MEASURES[measure].lower()} in {other_name}.")
                            elif mode in {"outcome_pct", "fatalities_per_1000"}:
                                st.caption("Each point's denominator is all records in that category and year within the current view." if series_field else "Each point's denominator is all records in that year within the current view.")
                            st.dataframe(annual, hide_index=True, width="stretch")
                        with st.expander("Population comparison", expanded=False):
                            show_comparison(data, view, other, "Current view: " + focus_name, other_name, mode, measure, outcome)
            with st.container(border=True, key="matrix_panel"):
                st.subheader("Compare two dimensions")
                r, c = st.columns(2)
                with r:
                    row_field = st.selectbox("Matrix rows", choices, index=choices.index("location_group"), format_func=field_label, key="matrix_rows")
                with c:
                    columns = [f for f in choices if f != row_field]
                    col_field = st.selectbox("Matrix columns", columns, index=columns.index("hazard_mechanism") if "hazard_mechanism" in columns else 0,
                                             format_func=field_label, key="matrix_columns")
                matrix = an.summarize_by(data, view, [row_field, col_field], measure, mode, outcome, other)
                st.caption(f"Showing up to {min(top_n, 15)} rows and columns, ranked by numerator totals. Select cells to inspect their records; unobserved combinations have no recorded accidents.")
                plot = charts.heatmap_figure(matrix, row_field, col_field, field_label(row_field), field_label(col_field), label, top_n=min(top_n, 15))
                plot.update_layout(clickmode="event+select",
                                  dragmode="pan" if selection_mode == "points" else "select")
                event = st.plotly_chart(plot, width="stretch", theme=None, on_select="rerun", selection_mode=selection_mode,
                                        key=f"matrix_{st.session_state.view_version}_{row_field}_{col_field}_{mode}_{measure}_{selection_mode}",
                                        config={"displaylogo": False, "modeBarButtonsToRemove": ["toImage"]})
                handle_selection(event, [row_field, col_field], "Matrix")
                with st.expander("Select a matrix cell using controls"):
                    x, y, action = st.columns([2, 2, 1])
                    with x:
                        rv = st.selectbox("Row value", sorted(matrix[row_field].unique().tolist(), key=str), key=f"cell_row_{row_field}_{st.session_state.view_version}")
                    with y:
                        cv = st.selectbox("Column value", sorted(matrix[col_field].unique().tolist(), key=str), key=f"cell_col_{col_field}_{st.session_state.view_version}")
                    with action:
                        if st.button("Inspect cell"):
                            add_drill(f"{rv} / {cv}", [[{"field": row_field, "op": "in", "value": [rv]}, {"field": col_field, "op": "in", "value": [cv]}]])
    with group_tab:
        with st.container(border=True, key="group_editor"):
            groups_panel(data, groups, reference_mask, focus_name)
    with records:
        records_panel(data, view)
    with context_tab:
        coverage_and_workforce(data, view, years)


if __name__ == "__main__":
    main()
