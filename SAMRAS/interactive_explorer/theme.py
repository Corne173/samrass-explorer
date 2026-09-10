"""Shared presentation tokens for the local SAMRASS analytics interface."""
from __future__ import annotations

import re

BACKGROUND = "#0B1120"
SURFACE = "#152237"
RAISED = "#203550"
TEXT = "#F4F7FC"
MUTED = "#C3CEE0"
BORDER = "#3B506A"
CONTROL_BORDER = "#7186A2"
GRID = "#30445F"
TEAL = "#72E5CF"
BLUE = "#9BC4FF"
AMBER = "#F5C57A"
CATEGORICAL = [TEAL, BLUE, AMBER, "#C9B7F6", "#ABDDA7", "#F5B1C1", "#9BDFEC"]

CSS = """
<style>
  :root {color-scheme:dark;--ink:#F4F7FC;--muted:#C3CEE0;--panel:#152237;
         --line:#3B506A;--accent:#72E5CF;--control:#1B2C43}
  .stApp {background:#0B1120;color:var(--ink)}
  [data-testid="stHeader"] {background:#0B1120}
  [data-testid="stSidebar"] {background:#101A2D;border-right:1px solid var(--line)}
  .block-container {padding:3.9rem 2rem 2.5rem;max-width:1660px}
  [data-testid="stSidebarUserContent"] {padding:1.4rem 1.15rem}
  [data-testid="stVerticalBlock"] {gap:.8rem}
  h1,h2,h3 {color:var(--ink);letter-spacing:-.025em}
  h1 {font-size:2rem!important;line-height:1.22!important;font-weight:650!important;padding:0!important}
  h3 {font-size:1.2rem!important;font-weight:600!important;padding:.2rem 0 .4rem!important}
  /* Streamlit otherwise dims captions to 60%, including denominator text. */
  [data-testid="stCaptionContainer"] {color:var(--muted)!important;opacity:1!important;
       font-size:.9rem!important;line-height:1.5!important}
  [data-testid="stCaptionContainer"] p {color:inherit;font-size:inherit;line-height:inherit}
  [data-testid="stWidgetLabel"] p {font-size:.9rem;color:#DFE7F3;font-weight:500;line-height:1.4}
  [data-baseweb="select"],input,textarea,button {font-size:.96rem!important}
  input::placeholder,textarea::placeholder {color:#C3CEE0!important;opacity:1!important}
  button:focus-visible,[role="tab"]:focus-visible {outline:2px solid var(--accent)!important;outline-offset:3px}
  [data-baseweb="select"]>div {border-radius:9px}
  [data-testid="stBaseButton-secondary"]:hover,[data-testid="stBaseButton-tertiary"]:hover {
       background:#263D57;border-color:var(--accent);color:var(--ink)}
  .app-heading {margin:0 0 .45rem}
  .app-heading p {margin:.4rem 0 0;color:var(--muted);font-size:.96rem;line-height:1.45}
  .eyebrow {color:#B9D2EB;font-size:.74rem;letter-spacing:.1em;font-weight:600;margin:0 0 .4rem}
  .sidebar-brand {display:flex;align-items:center;gap:.8rem;margin-bottom:.8rem}
  .brand-mark {display:grid;place-items:center;width:38px;height:38px;border:1px solid #62BBAE;
       border-radius:11px;background:#193E42;color:#9EF1E1;font-size:1.35rem}
  .brand-name {font-size:1.15rem;font-weight:650;letter-spacing:.025em}
  .brand-sub {font-size:.8rem;color:var(--muted);margin-top:.1rem}
  .sidebar-section {font-size:.88rem;color:var(--ink);font-weight:600;margin:.6rem 0 .1rem}
  .sidebar-section span {color:var(--accent);font-size:.82rem;margin-right:.55rem}
  [data-testid="stSidebar"] [data-testid="stExpander"] {margin-top:.2rem}
  .scope-line {display:flex;align-items:center;justify-content:space-between;gap:1rem;margin:.25rem 0 .2rem}
  .scope-name {font-size:1rem;font-weight:550;color:var(--ink);display:flex;align-items:center;gap:.6rem}
  .scope-name::before {content:"";width:7px;height:7px;background:var(--accent);border-radius:50%}
  .scope-period {color:var(--muted);font-size:.88rem;white-space:nowrap}
  [data-testid="stMetric"] {background:var(--panel);border:1px solid var(--line);border-radius:12px;
       padding:16px 18px;box-shadow:0 2px 8px #02081730}
  [data-testid="stMetricLabel"] p {color:#CED9EA;font-size:.9rem;font-weight:500}
  [data-testid="stMetricValue"] {color:var(--ink);font-size:2rem;font-weight:650;
       line-height:1.3;letter-spacing:-.025em;font-variant-numeric:tabular-nums}
  .st-key-population_summary [data-testid="stColumn"]:last-child [data-testid="stMetric"] {
       border-color:#609E99;background:#183437;box-shadow:inset 0 3px 0 #72E5CF}
  .st-key-population_summary [data-testid="stColumn"]:last-child [data-testid="stMetricValue"] {color:#A1F4E4}
  .st-key-ranked_panel,.st-key-trend_panel,.st-key-matrix_panel,.st-key-narrative_panel,
  .st-key-group_editor {background:var(--panel);border-radius:12px;border-color:var(--line)!important}
  .st-key-measure_controls {background:#121F32;padding:1rem!important;border-color:var(--line)!important}
  .measure-readout {padding:.1rem 0 .1rem 1rem;border-left:2px solid #53857F;min-height:70px}
  .measure-readout .measure-label {color:#CED9EA;font-size:.9rem;line-height:1.3;margin-bottom:.4rem}
  .measure-readout .measure-value {color:#A1F4E4;font-size:2rem;line-height:1.2;font-weight:650;
       letter-spacing:-.025em;font-variant-numeric:tabular-nums}
  [data-baseweb="tab-list"] {gap:.4rem;padding:.35rem;border:1px solid var(--line);border-radius:11px;
       background:#111E31;width:fit-content;max-width:100%}
  [data-baseweb="tab"] {height:2.6rem;padding:.35rem .9rem;border-radius:7px;
       font-weight:550;color:#D0DBEB;font-size:.95rem}
  [data-baseweb="tab"]:hover {background:#203550;color:var(--ink)}
  [data-baseweb="tab"][aria-selected="true"] {background:#24504F;color:#C7FFF1;
       box-shadow:inset 0 0 0 1px #4A8980}
  [data-baseweb="tab-highlight"],[data-baseweb="tab-border"] {display:none}
  [data-testid="stExpander"] details {border-color:var(--line);background:transparent}
  [data-testid="stExpander"] summary p {font-size:.95rem;color:#E0E9F6}
  [data-testid="stPlotlyChart"] {border-radius:8px;overflow:hidden}
  [data-testid="stText"] {white-space:pre-wrap;overflow-wrap:anywhere;line-height:1.7;
       font-family:inherit;font-size:1rem;color:var(--ink)}
  [data-testid="stPopoverBody"] {min-width:min(880px,calc(100vw - 3rem));background:var(--panel)}
  .st-key-chart_grid [data-testid="stHorizontalBlock"] {flex-wrap:wrap}
  .st-key-chart_grid [data-testid="stHorizontalBlock"]>[data-testid="stColumn"] {flex:1 1 420px!important;min-width:0}
  .st-key-measure_controls [data-testid="stHorizontalBlock"] {flex-wrap:wrap}
  .st-key-measure_controls [data-testid="stColumn"] {flex:1 1 180px!important;min-width:0}
  .st-key-measure_controls [data-testid="stColumn"]:nth-child(3) {flex:1.35 1 235px!important}
  .st-key-measure_controls [data-testid="stColumn"]:last-child {flex:.8 1 125px!important}
  .modebar {background:transparent!important}
  @media (min-width:641px) and (max-width:1180px) {
    [data-testid="stMetricLabel"] {min-height:2.6rem;align-items:flex-start}
    [data-testid="stMetricLabel"] p {white-space:normal!important;overflow:visible!important;text-overflow:clip!important}
  }
  @media (max-width:850px) {
    .block-container {padding:3.9rem 1rem 2rem}
    .scope-line {align-items:flex-start;flex-direction:column;gap:.4rem}
    .measure-readout {border-left:0;padding:0}
    [data-baseweb="tab-list"] {gap:.15rem}
    [data-baseweb="tab"] {padding:.35rem .6rem}
  }
</style>
"""


def readable_cell_text(color: str) -> str:
    """Choose black or white from the rendered cell colour's luminance."""
    if color.startswith("#"):
        rgb = [int(color[i:i + 2], 16) / 255 for i in (1, 3, 5)]
    else:
        rgb = [float(v) / 255 for v in re.findall(r"[0-9.]+", color)[:3]]
    linear = [v / 12.92 if v <= .04045 else ((v + .055) / 1.055) ** 2.4 for v in rgb]
    luminance = sum(v * w for v, w in zip(linear, (.2126, .7152, .0722)))
    return "#000000" if (luminance + .05) / .05 >= 1.05 / (luminance + .05) else "#FFFFFF"


def style_figure(figure, height=None):
    """Match chart surfaces, labels, legends, hover and interaction controls."""
    figure.update_layout(
        template="plotly_dark", paper_bgcolor=SURFACE, plot_bgcolor=SURFACE,
        font={"family": "Arial, sans-serif", "size": 14, "color": TEXT},
        hoverlabel={"bgcolor": RAISED, "bordercolor": CONTROL_BORDER,
                    "font": {"color": TEXT, "size": 14}, "align": "left"},
        modebar={"bgcolor": "rgba(0,0,0,0)", "color": MUTED, "activecolor": TEAL},
        legend={"font": {"color": TEXT, "size": 14}},
    )
    if height is not None:
        figure.update_layout(height=height)
    figure.update_xaxes(gridcolor=GRID, zerolinecolor=BORDER,
                       tickfont={"color": MUTED, "size": 13}, title_font={"color": TEXT, "size": 14}, automargin=True)
    figure.update_yaxes(gridcolor=GRID, zerolinecolor=BORDER,
                       tickfont={"color": MUTED, "size": 13}, title_font={"color": TEXT, "size": 14}, automargin=True)
    return figure
