"""Read-only data operations for the local SAMRASS interactive explorer.

The saved master is authoritative. This module never imports a producer script,
reclassifies its existing columns, or writes data or figures.
"""

from __future__ import annotations

from pathlib import Path
import re

import numpy as np
import pandas as pd


SAMRAS_DIR = Path(__file__).resolve().parents[1]
INPUT_CSV = SAMRAS_DIR / "samrass_analysis_outputs" / "samrass_consolidated_master.csv"
WORKFORCE_MD = SAMRAS_DIR / "samrass_analysis_outputs" / "samrass_commodity_workforce_2005_2024.md"
MISSING = "Missing / unknown"

FIELD_LABELS = {
    "year": "Year", "commodity": "Commodity", "region": "Region",
    "location_group": "Location group", "location_text": "Source location",
    "place_text": "Source place", "working_place": "Working place", "section": "Section",
    "hazard_mechanism": "Injury mechanism (derived)",
    "mining_method_group": "Mining method (inferred proxy)",
    "cause_text": "Assigned cause", "cause_code": "Assigned cause code",
    "occupation_text": "Occupation", "occupation_code": "Occupation code",
    "task_text": "Task", "activity_text": "Activity",
    "severity_group": "Severity", "evidence_tier": "Illumination evidence tier",
    "illumination_shortcoming": "Illumination shortcoming",
    "narrative_clue_groups": "Narrative clues (overlapping)",
    "illumination_candidate": "Main-screen candidate", "confirmed_or_probable": "Core Tier A/B record",
    "persons_injured": "Recorded persons injured", "persons_killed": "Recorded persons killed",
    "persons_disabled": "Recorded persons disabled", "allocated_days_lost": "Allocated days lost",
    "age_years": "Age (years)", "age_source": "Age source",
    "experience_years": "Experience / employment duration (years)",
    "experience_months": "Experience / employment duration (months)", "experience_source": "Experience source",
    "gender": "Gender", "employment_status": "Employment status",
    "contracting_company": "Contracting company", "day_of_week": "Day of week",
    "time_of_accident": "Recorded accident time", "depth_below_surface": "Depth below surface",
    "type_of_accident": "Accident type", "dangerous_occurrence": "Dangerous occurrence",
    "casualty_classification": "Casualty classification code",
    "casualty_classification_description": "Casualty classification",
    "body_part_injured": "Body part code", "body_part_injured_description": "Body part",
    "nature_of_injury": "Nature of injury code", "nature_of_injury_description": "Nature of injury",
    "accident_status": "Accident status", "inquiry_type": "Inquiry type",
    "accident_description": "Full accident narrative", "source_file": "Source file",
    "record_id": "Record ID", "regional_accident_no": "Regional accident number",
    "mine_accident_no": "Mine accident number",
    "drilling_context": "Drilling context (exploratory)",
    "production_or_coal_extraction": "Production or coal extraction setting",
    "active_drilling_in_production": "Active drilling in production / coal extraction",
}
NUMERIC_FIELDS = {
    "year", "source_year", "persons_injured", "persons_killed", "persons_disabled",
    "allocated_days_lost", "age_years", "experience_years", "experience_months", "depth_below_surface",
}
MEASURES = {
    "records": "Accident records", "injured": "Persons injured", "fatalities": "Persons killed",
    "disabled": "Persons disabled", "fatal_records": "Fatal accident records",
    "injury_records": "Records with persons injured", "core_records": "Core Tier A/B records",
}
OUTCOMES = {
    "all": "All records", "injury": "At least one person injured", "fatal": "At least one person killed",
    "disabled": "At least one person disabled", "core": "Core Tier A/B",
    "tier_a": "Tier A assigned-cause evidence", "tier_b": "Tier B narrative evidence",
    "candidate": "Main-screen illumination candidate",
}
WORKFORCE_COMMODITIES = {
    "AU": "Gold", "PT": "PGM", "CL": "Coal", "CR": "Chrome",
    "DI": "Diamonds", "FE": "Iron ore", "MN": "Manganese",
}
DRILLING_RECORDED = "Recorded active drilling"
DRILLING_NARRATIVE = "Narrative active drilling"
DRILLING_RELATED = "Drilling equipment handling or maintenance"
DRILLING_UNCERTAIN = "Ambiguous drilling mention"
DRILLING_NONE = "No drilling indication"
_METRIC_COLUMNS = ["value", "numerator", "denominator", "scale", "unit"]


def _text(df: pd.DataFrame, field: str) -> pd.Series:
    if field not in df:
        return pd.Series("", index=df.index, dtype=object)
    return df[field].fillna("").astype(str).str.strip()


def _numeric(df: pd.DataFrame, field: str) -> pd.Series:
    if field not in df:
        return pd.Series(np.nan, index=df.index, dtype=float)
    return pd.to_numeric(df[field], errors="coerce").replace([np.inf, -np.inf], np.nan)


def _boolean(series: pd.Series) -> pd.Series:
    if pd.api.types.is_bool_dtype(series):
        return series.fillna(False).astype(bool)
    return series.fillna("").astype(str).str.strip().str.lower().isin(["true", "1", "yes"])


def _mask(df: pd.DataFrame, mask=None) -> pd.Series:
    if mask is None:
        return pd.Series(True, index=df.index, dtype=bool)
    if isinstance(mask, pd.Series):
        return _boolean(mask.reindex(df.index, fill_value=False))
    if len(mask) != len(df):
        raise ValueError("The selection mask does not match the data length.")
    return _boolean(pd.Series(mask, index=df.index))


def _missing(series: pd.Series) -> pd.Series:
    missing = series.isna() | series.astype(str).str.strip().eq("")
    if pd.api.types.is_numeric_dtype(series):
        missing = missing | ~np.isfinite(series)
    return missing


def _add_exploratory_context(df: pd.DataFrame) -> pd.DataFrame:
    """Conservative activity clues; these are not illumination classifications."""
    activity = _text(df, "activity_text").str.lower()
    narrative = _text(df, "accident_description").str.lower()
    # Explicit source activities are more reliable than an incidental equipment word.
    recorded = activity.str.match(r"^(?:drilling(?:\b|\s*\()|collaring(?:\s+(?:a\s+)?hole)?\b)")
    related_activity = activity.str.contains(
        r"(?:transport|carry|carrying|load|unload|handling|repair|maintain|maintenance|install|remove|changing)",
        regex=True,
    ) & activity.str.contains(r"drill|borer|collar", regex=True)
    recorded &= ~related_activity
    mention = narrative.str.contains(r"\b(?:drill\w*|collar\w*|boring)\b", regex=True)
    # Require an action and its context, not a job title such as 'driller'.
    active = narrative.str.contains(
        r"\b(?:while|whilst|when|was|were|busy|during|started|continued)\s+"
        r"(?:(?:he|she|they|the\s+(?:injured|deceased|worker|employee))\s+)?"
        r"(?:(?:was|were|busy|with|the|actively|actually|in\s+the\s+process\s+of)\s+)*"
        r"(?:drilling|collaring)\b|\b(?:drilling|collaring)\s+(?:(?:a|the|blast|support|roof|new)\s+){0,3}holes?\b",
        regex=True,
    )
    related = narrative.str.contains(
        r"\b(?:carrying|carried|transporting|transported|moving|loading|unloading|offloading|"
        r"repairing|repair|maintaining|maintenance|installing|removing|changing|handling)\b"
        r"[^.;\n]{0,65}\b(?:drill\w*|borer)\b|"
        r"\b(?:drill\w*|borer)\b[^.;\n]{0,45}\b(?:transport|maintenance|repair|repairs)\b",
        regex=True,
    )
    negated = narrative.str.contains(
        r"\b(?:before|after|finished|completed|stopped|stop|not|wasn't|was not|were not|preparing\s+(?:for|to))"
        r"\s+(?:(?:he|she|they|had|was|were|the|with|drilling\s+was)\s+){0,3}(?:drilling|collaring)\b",
        regex=True,
    )
    context = pd.Series(DRILLING_NONE, index=df.index, dtype=object)
    context.loc[mention | recorded | related_activity] = DRILLING_UNCERTAIN
    context.loc[related | related_activity] = DRILLING_RELATED
    context.loc[active & ~related & ~negated & ~related_activity] = DRILLING_NARRATIVE
    # Explicit completed-drilling/handling wording overrides a broad source activity.
    context.loc[recorded & ~related & ~negated] = DRILLING_RECORDED
    df["drilling_context"] = context
    location = _text(df, "location_text").str.lower()
    broad_production = _text(df, "location_group").eq("Stope, face, or production area")
    coal_extraction = _text(df, "commodity").eq("CL") & (
        location.str.contains(r"\b(?:bord|pillar|longwall|shortwall|working\s+face|coal\s*face)\b", regex=True)
        | broad_production
    )
    df["production_or_coal_extraction"] = broad_production | coal_extraction
    df["active_drilling_in_production"] = df["production_or_coal_extraction"] & context.isin(
        [DRILLING_RECORDED, DRILLING_NARRATIVE]
    )
    return df


def load_data(path: Path | str = INPUT_CSV) -> pd.DataFrame:
    """Load saved fields as strings first so identifiers and literal N/A survive."""
    df = pd.read_csv(path, dtype=str, keep_default_na=False, encoding="utf-8-sig")
    required = {
        "record_id", "year", "commodity", "location_text", "location_group", "hazard_mechanism",
        "accident_description", "persons_injured", "persons_killed", "persons_disabled",
        "evidence_tier", "illumination_candidate", "confirmed_or_probable",
    }
    absent = sorted(required - set(df.columns))
    if absent:
        raise ValueError("The saved master is missing required columns: " + ", ".join(absent))
    if _text(df, "record_id").eq("").any() or df["record_id"].duplicated().any():
        raise ValueError("The saved master must contain nonblank, unique record_id values.")
    for field in NUMERIC_FIELDS & set(df.columns):
        df[field] = _numeric(df, field)
    if df["year"].isna().any() or (df["year"] % 1 != 0).any():
        raise ValueError("Every saved accident record must have a valid integer year.")
    df["year"] = df["year"].astype(int)
    for field in ("illumination_candidate", "confirmed_or_probable"):
        tokens = _text(df, field).str.lower()
        if not tokens.isin(["true", "false", "1", "0", "yes", "no", ""]).all():
            raise ValueError(f"Unrecognised boolean values in {field}.")
        df[field] = _boolean(df[field])
    return _add_exploratory_context(df)


def category_series(df: pd.DataFrame, field: str) -> pd.Series:
    if field not in df:
        raise ValueError(f"Unknown field: {field}")
    values = df[field].astype(object).copy()
    return values.mask(_missing(df[field]), MISSING)


def apply_rules(df: pd.DataFrame, rules: list[dict], logic: str = "AND") -> pd.Series:
    logic = logic.upper()
    if logic not in {"AND", "OR"}:
        raise ValueError("Rule logic must be AND or OR.")
    if not rules:
        return _mask(df)
    result = pd.Series(logic == "AND", index=df.index, dtype=bool)
    for rule in rules:
        field, op, value = rule["field"], rule["op"], rule.get("value")
        if field not in df:
            raise ValueError(f"Unknown rule field: {field}")
        if op in {"is_missing", "not_missing"}:
            current = _missing(df[field])
            if op == "not_missing":
                current = ~current
        elif op in {"in", "not_in"}:
            values = value if isinstance(value, (list, tuple, set)) else [value]
            current = category_series(df, field).isin(values)
            if op == "not_in":
                current = ~current
        elif op in {"contains", "not_contains"}:
            current = _text(df, field).str.contains(str(value or ""), case=False, regex=False)
            if op == "not_contains":
                current = ~current
        elif op in {"between", "gte", "lte"}:
            numeric = _numeric(df, field)
            if op == "between":
                if not isinstance(value, (list, tuple)) or len(value) != 2:
                    raise ValueError("A between rule needs [minimum, maximum].")
                lower, upper = map(float, value)
                if not np.isfinite([lower, upper]).all() or lower > upper:
                    raise ValueError("Numeric bounds must be finite and ordered.")
                current = numeric.between(lower, upper, inclusive="both")
            else:
                boundary = float(value)
                if not np.isfinite(boundary):
                    raise ValueError("Numeric boundaries must be finite.")
                current = numeric.ge(boundary) if op == "gte" else numeric.le(boundary)
        else:
            raise ValueError(f"Unknown rule operator: {op}")
        current = current.fillna(False)
        result = result & current if logic == "AND" else result | current
    return result


def preset_groups() -> dict[str, dict]:
    return {
        "Production areas": {
            "parent": "Reference population", "logic": "AND",
            "rules": [{"field": "location_group", "op": "in", "value": ["Stope, face, or production area"]}],
        },
        "Stope working face": {
            "parent": "Production areas", "logic": "AND",
            "rules": [{"field": "location_text", "op": "in", "value": ["Stope working face"]}],
        },
        "Coal extraction settings": {
            "parent": "Reference population", "logic": "AND",
            "rules": [{"field": "commodity", "op": "in", "value": ["CL"]},
                      {"field": "production_or_coal_extraction", "op": "in", "value": [True]}],
        },
        "Active drilling in production / coal extraction": {
            "parent": "Reference population", "logic": "AND",
            "rules": [{"field": "active_drilling_in_production", "op": "in", "value": [True]}],
        },
    }


def resolve_group_mask(df: pd.DataFrame, name: str, groups: dict, reference_mask) -> pd.Series:
    reference = _mask(df, reference_mask)
    visiting: set[str] = set()
    resolved: dict[str, pd.Series] = {"Reference population": reference}

    def resolve(group_name: str) -> pd.Series:
        if group_name in resolved:
            return resolved[group_name]
        if group_name in visiting:
            raise ValueError(f"Group parent cycle involving {group_name}.")
        if group_name not in groups:
            raise ValueError(f"Unknown group: {group_name}")
        visiting.add(group_name)
        group = groups[group_name]
        parent = group.get("parent", "Reference population")
        if parent == "All SAMRASS":
            raise ValueError("All SAMRASS is a comparison only; groups must descend from Reference population.")
        parent_mask = resolve(parent)
        resolved[group_name] = parent_mask & apply_rules(df, group.get("rules", []), group.get("logic", "AND"))
        visiting.remove(group_name)
        return resolved[group_name]

    return _mask(df) if name == "All SAMRASS" else resolve(name)


def outcome_mask(df: pd.DataFrame, outcome: str | pd.Series) -> pd.Series:
    if isinstance(outcome, pd.Series):
        return _mask(df, outcome)
    if outcome == "all":
        return _mask(df)
    numeric = {"injury": "persons_injured", "fatal": "persons_killed", "disabled": "persons_disabled"}
    if outcome in numeric:
        return _numeric(df, numeric[outcome]).gt(0)
    if outcome in {"core", "candidate"}:
        field = "confirmed_or_probable" if outcome == "core" else "illumination_candidate"
        return _boolean(df[field])
    if outcome in {"tier_a", "tier_b"}:
        return _text(df, "evidence_tier").str.startswith("Tier A" if outcome == "tier_a" else "Tier B")
    raise ValueError(f"Unknown outcome: {outcome}")


def _measure_series(df: pd.DataFrame, measure: str) -> pd.Series:
    if measure == "records":
        return pd.Series(1, index=df.index, dtype=int)
    counts = {"injured": "persons_injured", "fatalities": "persons_killed", "disabled": "persons_disabled"}
    if measure in counts:
        return _numeric(df, counts[measure]).fillna(0)
    outcomes = {"fatal_records": "fatal", "injury_records": "injury", "core_records": "core"}
    if measure in outcomes:
        return outcome_mask(df, outcomes[measure]).astype(int)
    raise ValueError(f"Unknown measure: {measure}")


def measure_total(frame: pd.DataFrame, measure: str) -> float:
    return float(_measure_series(frame, measure).sum())


def _metric_result(numerator: float, denominator: float, scale: int, unit: str) -> dict:
    value = float(numerator) if scale == 1 and pd.isna(denominator) else (
        float(numerator) / float(denominator) * scale if denominator > 0 and np.isfinite(denominator) else np.nan
    )
    return {"value": value, "numerator": float(numerator), "denominator": float(denominator), "scale": scale, "unit": unit}


def calculate_metric(df: pd.DataFrame, mask, measure: str = "records", mode: str = "total",
                     outcome: str | pd.Series = "fatal", denominator_mask=None) -> dict:
    selected = _mask(df, mask)
    if mode == "total":
        return _metric_result(measure_total(df.loc[selected], measure), np.nan, 1, MEASURES[measure])
    if mode == "share":
        denominator = measure_total(df.loc[_mask(df, denominator_mask)], measure)
        return _metric_result(measure_total(df.loc[selected], measure), denominator, 100, "Percent")
    if mode == "outcome_pct":
        return _metric_result(int((selected & outcome_mask(df, outcome)).sum()), int(selected.sum()), 100, "Percent")
    if mode == "fatalities_per_1000":
        return _metric_result(measure_total(df.loc[selected], "fatalities"), int(selected.sum()), 1000,
                              "Persons killed per 1,000 accident records")
    raise ValueError(f"Unknown metric mode: {mode}")


def summarize_by(df: pd.DataFrame, mask, fields: list[str], measure: str = "records", mode: str = "total",
                 outcome: str | pd.Series = "fatal", denominator_mask=None) -> pd.DataFrame:
    fields = list(dict.fromkeys(fields))
    selected = _mask(df, mask)
    if not fields:
        return pd.DataFrame([calculate_metric(df, selected, measure, mode, outcome, denominator_mask)])
    work = pd.DataFrame({field: category_series(df, field).loc[selected] for field in fields})
    if mode in {"total", "share"}:
        values = _measure_series(df, measure)
        scale = 1 if mode == "total" else 100
        unit = MEASURES[measure] if mode == "total" else "Percent"
        common_denominator = np.nan if mode == "total" else measure_total(df.loc[_mask(df, denominator_mask)], measure)
    elif mode == "outcome_pct":
        values, scale, unit = outcome_mask(df, outcome).astype(int), 100, "Percent"
        common_denominator = None
    elif mode == "fatalities_per_1000":
        values, scale, unit = _measure_series(df, "fatalities"), 1000, "Persons killed per 1,000 accident records"
        common_denominator = None
    else:
        raise ValueError(f"Unknown metric mode: {mode}")
    work["__numerator"] = values.loc[selected]
    rows = []
    grouper = fields[0] if len(fields) == 1 else fields
    for key, part in work.groupby(grouper, dropna=False, sort=False):
        key = (key,) if len(fields) == 1 else key
        denominator = len(part) if common_denominator is None else common_denominator
        rows.append(dict(zip(fields, key)) | _metric_result(part["__numerator"].sum(), denominator, scale, unit))
    return pd.DataFrame(rows, columns=fields + _METRIC_COLUMNS)


def summarize_annual(df: pd.DataFrame, mask, years: tuple[int, int], measure: str = "records",
                     mode: str = "total", outcome: str | pd.Series = "fatal", denominator_mask=None,
                     category_field: str | None = None, categories: list | None = None) -> pd.DataFrame:
    """Complete the year/category grid, preserving the explorer's denominators.

    Shares use the chosen comparison population across its full period, just
    like the ranked bars. Within-group rates use each category/year's records.
    Absent combinations have zero totals and undefined within-group rates.
    """
    if years[0] > years[1]:
        raise ValueError("The start year must not follow the end year")
    if category_field == "year":
        raise ValueError("The annual category must be different from year")
    fields = ["year"] + ([category_field] if category_field else [])
    table = summarize_by(df, mask, fields, measure, mode, outcome, denominator_mask)
    annual_years = list(range(years[0], years[1] + 1))
    if category_field:
        values = list(dict.fromkeys(categories if categories is not None else table[category_field].tolist()))
        grid = pd.MultiIndex.from_product([annual_years, values], names=fields)
    else:
        grid = pd.Index(annual_years, name="year")
    table = table.set_index(fields).reindex(grid).reset_index()
    absent = table["unit"].isna()
    empty_metric = calculate_metric(df, pd.Series(False, index=df.index), measure, mode, outcome, denominator_mask)
    for column, value in empty_metric.items():
        table.loc[absent, column] = value
    table["year"] = table["year"].astype(int)
    return table


def coverage(df: pd.DataFrame, mask, fields: list[str]) -> pd.DataFrame:
    selected = df.loc[_mask(df, mask)]
    rows = []
    for field in fields:
        if field not in df:
            raise ValueError(f"Unknown coverage field: {field}")
        missing = int(_missing(selected[field]).sum())
        available = len(selected) - missing
        rows.append({"field": field, "available": available, "missing": missing,
                     "percent": available / len(selected) * 100 if len(selected) else np.nan})
    return pd.DataFrame(rows, columns=["field", "available", "missing", "percent"])


def load_workforce(path: Path | str = WORKFORCE_MD) -> pd.DataFrame:
    rows, in_table = [], False
    for line in Path(path).read_text(encoding="utf-8-sig").splitlines():
        line = line.strip()
        if line == "## Consolidated Long Table":
            in_table = True
            continue
        if in_table and line.startswith("## "):
            break
        if not in_table or not line.startswith("|"):
            continue
        cells = [cell.strip() for cell in line.strip("|").split("|")]
        if len(cells) != 7 or not cells[0].isdigit() or cells[1] not in WORKFORCE_COMMODITIES:
            continue
        rows.append({"year": int(cells[0]), "commodity": cells[1], "commodity_label": cells[2],
                     "employees": pd.to_numeric(cells[3].replace(",", ""), errors="coerce"),
                     "source": cells[4], "source_detail": cells[5], "notes": cells[6]})
    table = pd.DataFrame(rows, columns=["year", "commodity", "commodity_label", "employees", "source", "source_detail", "notes"])
    if table.empty or table.duplicated(["commodity", "year"]).any():
        raise ValueError("The workforce table is empty or has duplicate commodity/year denominators.")
    return table


def workforce_rates(df: pd.DataFrame, years, commodities, measure: str = "records", pooled: bool = False) -> pd.DataFrame:
    """Full-population commodity rates; deliberately accepts no subgroup mask.

    Pass the unfiltered saved master. This separate view is not a workplace,
    occupation, demographic, or drilling exposure-rate calculation.
    """
    years = sorted(set(int(year) for year in years))
    commodities = list(dict.fromkeys(commodities))
    invalid = set(commodities) - set(WORKFORCE_COMMODITIES)
    if invalid:
        raise ValueError("Workforce rates support only the seven disjoint major commodities: " + ", ".join(sorted(invalid)))
    if measure not in MEASURES:
        raise ValueError(f"Unknown measure: {measure}")
    columns = ["commodity", "commodity_label", "year", "numerator", "denominator", "value", "scale", "unit", "source"]
    if not years or not commodities:
        return pd.DataFrame(columns=columns if not pooled else [c for c in columns if c != "year"] + ["years", "period"])
    grid = pd.MultiIndex.from_product([commodities, years], names=["commodity", "year"]).to_frame(index=False)
    grid = grid.merge(load_workforce(), on=["commodity", "year"], how="left", validate="one_to_one")
    valid = pd.to_numeric(grid["employees"], errors="coerce")
    if (~np.isfinite(valid) | valid.le(0)).any():
        absent = grid.loc[~np.isfinite(valid) | valid.le(0), ["commodity", "year"]].to_dict("records")
        raise ValueError(f"No positive workforce denominator is available for: {absent}")
    selected = df["commodity"].isin(commodities) & df["year"].isin(years)
    counts = df.loc[selected, ["commodity", "year"]].copy()
    counts["numerator"] = _measure_series(df, measure).loc[selected]
    counts = counts.groupby(["commodity", "year"], as_index=False)["numerator"].sum()
    grid = grid.merge(counts, on=["commodity", "year"], how="left", validate="one_to_one")
    grid["numerator"] = grid["numerator"].fillna(0)
    grid = grid.rename(columns={"employees": "denominator"})
    if pooled:
        grid = grid.groupby(["commodity", "commodity_label"], as_index=False, sort=False).agg(
            numerator=("numerator", "sum"), denominator=("denominator", "sum"),
            years=("year", "nunique"), source=("source", lambda s: "; ".join(dict.fromkeys(s))),
        )
        grid["period"] = f"{years[0]}–{years[-1]}" if years == list(range(years[0], years[-1] + 1)) else ", ".join(map(str, years))
    grid["value"] = grid["numerator"] / grid["denominator"] * 1000
    grid["scale"] = 1000
    grid["unit"] = MEASURES[measure] + (" per 1,000 employee-years" if pooled else " per 1,000 employees")
    return grid[[c for c in columns if c != "year"] + ["years", "period"]] if pooled else grid[columns]
