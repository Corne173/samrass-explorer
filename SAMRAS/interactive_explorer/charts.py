"""In-memory Plotly figures for the SAMRASS interactive explorer.

Every selectable point keeps its original grouping keys in ``customdata``.
The cell matrix uses selectable square scatter markers because Streamlit's
native Plotly selection events do not consistently include heatmap cells.
"""

from __future__ import annotations

from html import escape
from textwrap import wrap

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.colors import sample_colorscale


import theme

TEXT = theme.TEXT
TEAL = theme.TEAL
AMBER = theme.AMBER
GRID = theme.BORDER
COLOR_SCALE = [[0, "#28425C"], [0.45, "#479D9A"], [1, "#A2F0DC"]]
NUMERIC_COLUMNS = ("value", "numerator", "denominator", "scale")


def _wrapped(value: object, width: int = 30) -> str:
    lines = wrap(str(value), width=width, break_long_words=False, break_on_hyphens=False)
    return "<br>".join(escape(line) for line in lines) or " "


def _axis_label(value: object, width: int = 25) -> str:
    lines = wrap(str(value), width=width, break_long_words=False, break_on_hyphens=False)
    if len(lines) > 2:
        lines = lines[:2]
        lines[-1] += "..."
    return "<br>".join(escape(line) for line in lines) or " "


def _number(value: object, decimals: int = 0) -> str:
    if pd.isna(value) or not np.isfinite(float(value)):
        return "Undefined"
    return f"{float(value):,.{decimals}f}"


def _is_percent(unit: object, metric_label: str) -> bool:
    wording = f"{unit} {metric_label}".lower()
    return "percent" in wording or "%" in wording


def _value_label(row: pd.Series, metric_label: str) -> str:
    value = row["value"]
    if pd.isna(value):
        return "Undefined"
    if _is_percent(row["unit"], metric_label):
        return f"{_number(value, 1)}%"
    is_rate = "per " in str(row["unit"]).lower() or row["scale"] != 1
    return _number(value, 2 if is_rate else 0)


def _hover(row: pd.Series, fields: list[tuple[str, str]], metric_label: str) -> str:
    labels = [f"<b>{escape(label)}:</b> {_wrapped(row[field], 55)}" for field, label in fields]
    labels.append(f"<b>{escape(metric_label)}:</b> {_value_label(row, metric_label)}")
    labels.append(f"Numerator: {_number(row['numerator'])}")
    if pd.isna(row["denominator"]) and row["scale"] == 1:
        labels.append("Denominator: not applicable (total)")
    else:
        labels.append(f"Denominator: {_number(row['denominator'])}")
        if pd.notna(row["scale"]):
            labels.append(f"Scale: {_number(row['scale'])}")
    labels.append(f"Unit: {escape(str(row['unit']))}")
    return "<br>".join(labels)


def _prepare(table: pd.DataFrame, fields: list[str]) -> pd.DataFrame:
    required = fields + list(NUMERIC_COLUMNS) + ["unit"]
    absent = [column for column in required if column not in table.columns]
    if absent and not table.empty:
        raise ValueError(f"Missing chart columns: {', '.join(absent)}")
    work = table.reindex(columns=required).copy()
    for column in NUMERIC_COLUMNS:
        work[column] = pd.to_numeric(work[column], errors="coerce").replace([np.inf, -np.inf], np.nan)
    return work


def _base(height: int = 380) -> go.Figure:
    figure = theme.style_figure(go.Figure(), height)
    figure.update_layout(
        margin={"l": 15, "r": 38, "t": 18, "b": 55},
        showlegend=False, clickmode="event+select", dragmode="pan",
    )
    return figure


def _empty() -> go.Figure:
    figure = _base(320)
    figure.add_annotation(
        x=0.5, y=0.5, xref="paper", yref="paper", text="No records match", showarrow=False
    )
    figure.update_xaxes(visible=False)
    figure.update_yaxes(visible=False)
    return figure


def _axis_format(table: pd.DataFrame, metric_label: str) -> dict[str, object]:
    percent = any(_is_percent(unit, metric_label) for unit in table["unit"])
    rates = percent or any("per " in str(unit).lower() for unit in table["unit"])
    return {"tickformat": ",.1f" if rates else ",.0f", "ticksuffix": "%" if percent else ""}


def ranked_categories(table: pd.DataFrame, field: str, top_n: int) -> pd.DataFrame:
    """Use one stable ranking for both bars and the displayed annual series."""
    if top_n < 1:
        raise ValueError("top_n must be at least one")
    work = table.assign(_tie=table[field].map(str))
    return work.sort_values(
        ["value", "_tie"], ascending=[False, True], na_position="last", kind="stable"
    ).head(top_n).drop(columns="_tie")


def bar_figure(
    table: pd.DataFrame, field: str, label: str, metric_label: str, top_n: int = 15
) -> go.Figure:
    """Rank categories by their selected metric; retain raw keys for selection."""
    work = _prepare(table, [field])
    if work.empty:
        return _empty()
    work = ranked_categories(work, field, top_n)
    figure = _base(max(320, min(850, 70 + 38 * len(work))))
    figure.add_trace(
        go.Bar(
            x=work["value"].tolist(),
            y=list(range(len(work))),
            orientation="h",
            customdata=[[value] for value in work[field]],
            marker={"color": TEAL, "line": {"width": 0}, "cornerradius": 4},
            text=[_value_label(row, metric_label) for _, row in work.iterrows()],
            textposition="outside",
            textfont={"color": TEXT, "size": 14},
            cliponaxis=False,
            hovertext=[_hover(row, [(field, label)], metric_label) for _, row in work.iterrows()],
            hovertemplate="%{hovertext}<extra></extra>",
            selected={"marker": {"color": AMBER, "opacity": 1}},
            unselected={"marker": {"opacity": 0.85}},
        )
    )
    figure.update_yaxes(
        tickmode="array", tickvals=list(range(len(work))),
        ticktext=[_axis_label(value, 25) for value in work[field]],
        autorange="reversed", title_text=None, ticklabelstandoff=8, showgrid=False, zeroline=False,
    )
    figure.update_layout(bargap=0.34, margin={"l": 182, "r": 45, "t": 18, "b": 55})
    finite_values = work["value"].dropna()
    maximum = finite_values.max() if not finite_values.empty else 0
    figure.update_xaxes(title_text=metric_label, range=[0, max(1, maximum * 1.18)], **_axis_format(work, metric_label))
    for position, (_, row) in enumerate(work.iterrows()):
        if pd.isna(row["value"]):
            figure.add_annotation(
                x=0.015, xref="paper", y=position, yref="y", text="Undefined",
                xanchor="left", showarrow=False, hovertext=_hover(row, [(field, label)], metric_label),
            )
    return figure


def trend_figure(table: pd.DataFrame, metric_label: str, series_field: str | None = None,
                 series_label: str | None = None) -> go.Figure:
    """Show a total or category series; point selections retain year/category pairs."""
    fields = ["year"] + ([series_field] if series_field else [])
    work = _prepare(table, fields)
    if work.empty:
        return _empty()
    work = work.sort_values("year", kind="stable")
    figure = _base(560 if series_field else 430)
    groups = work.groupby(series_field, sort=False, dropna=False) if series_field else [("Total", work)]
    hover_fields = [("year", "Year")] + ([(series_field, series_label or series_field)] if series_field else [])
    for index, (name, part) in enumerate(groups):
        colour = theme.CATEGORICAL[index % len(theme.CATEGORICAL)] if series_field else theme.BLUE
        style = index // len(theme.CATEGORICAL) if series_field else 0
        figure.add_trace(
            go.Scatter(
                name=_axis_label(name, 25),
                x=part["year"].tolist(), y=part["value"].tolist(), mode="lines+markers",
                customdata=part[fields].to_numpy().tolist(),
                line={"color": colour, "width": 2.5, "dash": ["solid", "dash", "dot", "dashdot", "longdash"][style % 5]},
                marker={"color": colour if series_field else TEAL, "size": 7 if series_field else 9,
                        "symbol": ["circle", "diamond", "square", "triangle-up", "cross"][style % 5],
                        "line": {"color": theme.SURFACE, "width": 1}},
                connectgaps=False,
                hovertext=[_hover(row, hover_fields, metric_label) for _, row in part.iterrows()],
                hovertemplate="%{hovertext}<extra></extra>",
                selected={"marker": {"color": AMBER, "size": 12, "opacity": 1}},
                unselected={"marker": {"opacity": 0.65}},
            )
        )
    if series_field:
        figure.update_layout(showlegend=True, margin={"l": 15, "r": 25, "t": 18, "b": 200},
                             legend={"orientation": "h", "y": -0.25, "x": 0,
                                     "entrywidth": 0.5, "entrywidthmode": "fraction", "maxheight": 155,
                                     "font": {"size": 12}})
    years = work["year"].drop_duplicates().tolist()
    ticks = years[::max(1, (len(years) + 5) // 6)]
    if years[-1] not in ticks:
        ticks.append(years[-1])
    figure.update_xaxes(title_text="Year", tickmode="array", tickvals=ticks, tickformat="d")
    figure.update_xaxes(showgrid=False)
    figure.update_yaxes(title_text=metric_label, rangemode="tozero", griddash="dot", **_axis_format(work, metric_label))
    return figure


def _rank_categories(work: pd.DataFrame, field: str, top_n: int) -> list[object]:
    totals = work.groupby(field, dropna=False, sort=False)["numerator"].sum(min_count=1).reset_index()
    totals["_tie"] = totals[field].map(str)
    return totals.sort_values(
        ["numerator", "_tie"], ascending=[False, True], na_position="last", kind="stable"
    )[field].head(top_n).tolist()


def heatmap_figure(
    table: pd.DataFrame, row_field: str, col_field: str, row_label: str,
    col_label: str, metric_label: str, top_n: int = 12,
) -> go.Figure:
    """Return a selectable cell matrix ranked by summed numerators, not rates.

    Square scatter markers provide Plotly point-selection events in Streamlit.
    Missing combinations and undefined rates remain uncoloured cells.
    """
    if row_field == col_field:
        raise ValueError("The cell matrix requires two different grouping fields")
    work = _prepare(table, [row_field, col_field])
    if work.empty:
        return _empty()
    if top_n < 1:
        raise ValueError("top_n must be at least one")
    if work.duplicated([row_field, col_field]).any():
        raise ValueError("Each matrix combination must have exactly one aggregate row")
    rows = _rank_categories(work, row_field, top_n)
    columns = _rank_categories(work, col_field, top_n)
    cells = work.set_index([row_field, col_field]).reindex(
        pd.MultiIndex.from_product([rows, columns], names=[row_field, col_field])
    ).reset_index()
    row_positions = {value: index for index, value in enumerate(rows)}
    col_positions = {value: index for index, value in enumerate(columns)}
    cells["_x"] = cells[col_field].map(col_positions)
    cells["_y"] = cells[row_field].map(row_positions)
    height = max(320, min(900, 200 + 52 * len(rows)))
    marker_size = max(22, min(62, 580 / len(columns), (height - 190) / len(rows)) * 0.9)
    figure = _base(height)
    figure.update_layout(margin={"l": 30, "r": 125, "t": 25, "b": 150})
    fields = [(row_field, row_label), (col_field, col_label)]
    finite = cells[cells["value"].notna()]
    undefined = cells[cells["value"].isna()]
    maximum = finite["value"].max() if not finite.empty else 1
    maximum = max(1e-12, maximum)
    if not finite.empty:
        cell_colours = sample_colorscale(COLOR_SCALE, (finite["value"] / maximum).tolist())
        figure.add_trace(
            go.Scatter(
                x=finite["_x"].tolist(), y=finite["_y"].tolist(), mode="markers+text",
                customdata=finite[[row_field, col_field]].to_numpy().tolist(),
                marker={
                    "symbol": "square", "size": marker_size, "color": finite["value"].tolist(),
                    "colorscale": COLOR_SCALE, "cmin": 0, "cmax": maximum,
                    "showscale": True, "line": {"color": theme.SURFACE, "width": 1},
                    "colorbar": {
                        "title": {"text": _wrapped(metric_label, 20), "side": "right"},
                        "thickness": 12, "len": 0.85, "outlinewidth": 0, "tickfont": {"color": theme.MUTED}, **_axis_format(work, metric_label),
                    },
                },
                text=[_value_label(row, metric_label) for _, row in finite.iterrows()],
                textfont={
                    "size": 12,
                    "color": [theme.readable_cell_text(colour) for colour in cell_colours],
                },
                hovertext=[_hover(row, fields, metric_label) for _, row in finite.iterrows()],
                hovertemplate="%{hovertext}<extra></extra>",
                selected={"marker": {"opacity": 1}},
                unselected={"marker": {"opacity": 1}},
            )
        )
    if not undefined.empty:
        hover = []
        for _, row in undefined.iterrows():
            if pd.isna(row["unit"]):
                labels = [f"<b>{escape(label)}:</b> {_wrapped(row[field], 55)}" for field, label in fields]
                hover.append("<br>".join(labels + ["No aggregate for this combination", "Numerator: unavailable", "Denominator: unavailable"]))
            else:
                hover.append(_hover(row, fields, metric_label))
        figure.add_trace(
            go.Scatter(
                x=undefined["_x"].tolist(), y=undefined["_y"].tolist(), mode="markers+text",
                customdata=undefined[[row_field, col_field]].to_numpy().tolist(),
                marker={"symbol": "square", "size": marker_size, "color": theme.RAISED, "line": {"color": GRID, "width": 1}},
                text=["—"] * len(undefined), textfont={"color": TEXT, "size": 12},
                hovertext=hover, hovertemplate="%{hovertext}<extra></extra>",
                selected={"marker": {"color": AMBER, "opacity": 1}},
                unselected={"marker": {"opacity": 0.4}},
            )
        )
    figure.update_xaxes(
        title_text=col_label, tickmode="array", tickvals=list(range(len(columns))),
        ticktext=[_axis_label(value, 20) for value in columns], tickangle=-35,
        range=[-0.65, len(columns) - 0.35], showgrid=False, zeroline=False,
    )
    figure.update_yaxes(
        title_text=row_label, tickmode="array", tickvals=list(range(len(rows))),
        ticktext=[_axis_label(value, 29) for value in rows],
        range=[len(rows) - 0.35, -0.65], showgrid=False, zeroline=False,
    )
    return figure
