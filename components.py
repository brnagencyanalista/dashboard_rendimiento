"""
components.py — Componentes de UI del dashboard
================================================
Todas las funciones de renderizado (Streamlit + Plotly).
No contiene lógica de negocio ni acceso a archivos.
"""

import streamlit as st
import pandas as pd
import plotly.graph_objects as go

from config import (
    C_CHELSEA, C_KATIUSKA, C_KARINA,
    AZUL, VERDE, NARANJA, VIOLETA, ROSA, CYAN,
    COLOR_ASESORA,
)

# ── Estilos CSS ───────────────────────────────────────────────────────────────

CSS = """
<style>
  html, body, .stApp,
  [data-testid="stAppViewContainer"],
  [data-testid="stSidebar"],
  section[data-testid="stSidebar"] > div,
  .block-container, [data-testid="block-container"] {
    background-color: #F1F5F9 !important;
  }
  [data-testid="stSidebar"] {
    background-color: #FFFFFF !important;
    box-shadow: 2px 0 8px rgba(0,0,0,.07) !important;
    border-right: none !important;
  }
  .kpi-grid { display: flex; gap: 14px; margin-bottom: 6px; }
  .kpi-card {
    flex: 1;
    background: #FFFFFF;
    border-radius: 16px;
    padding: 20px 16px 16px;
    text-align: center;
    box-shadow: 0 2px 8px rgba(0,0,0,.07);
    border-top: 4px solid var(--accent);
  }
  .kpi-label {
    font-size: 0.66rem; color: #94A3B8;
    text-transform: uppercase; letter-spacing: .09em; margin-bottom: 6px;
  }
  .kpi-value { font-size: 2.2rem; font-weight: 800; line-height: 1; color: var(--accent); }
  .kpi-sub   { font-size: 0.72rem; color: #CBD5E1; margin-top: 5px; }
  .chart-card {
    background: #FFFFFF;
    border-radius: 16px;
    padding: 4px 4px 0;
    box-shadow: 0 2px 8px rgba(0,0,0,.06);
    margin-bottom: 14px;
  }
  .section-lbl {
    font-size: 0.68rem; color: #64748B;
    text-transform: uppercase; letter-spacing: .1em;
    margin: 22px 0 10px 2px;
    border-left: 3px solid #6366F1; padding-left: 8px;
    font-weight: 700;
  }
</style>
"""

# ── Plotly layout base ────────────────────────────────────────────────────────

_L = dict(
    paper_bgcolor="#FFFFFF",
    plot_bgcolor="#FFFFFF",
    font=dict(family="Inter, sans-serif", color="#1E293B", size=12),
    margin=dict(t=72, b=36, l=52, r=44),
    legend=dict(
        bgcolor="rgba(255,255,255,0)", borderwidth=0,
        orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1,
        font=dict(size=11),
    ),
    hoverlabel=dict(bgcolor="white", bordercolor="#E2E8F0",
                    font=dict(size=12, family="Inter, sans-serif")),
)
_G = dict(showgrid=True, gridcolor="#F1F5F9", zeroline=False, tickfont=dict(size=11))

_CHART = '<div class="chart-card">'
_CHART_END = '</div>'


# ── Tarjeta KPI ───────────────────────────────────────────────────────────────

def _kpi(col, label: str, value: str, sub: str, accent: str) -> None:
    col.markdown(
        f'<div class="kpi-card" style="--accent:{accent}">'
        f'<div class="kpi-label">{label}</div>'
        f'<div class="kpi-value">{value}</div>'
        f'<div class="kpi-sub">{sub}&nbsp;</div></div>',
        unsafe_allow_html=True,
    )


def render_kpis(df_v: pd.DataFrame, df_leads_filt: pd.DataFrame) -> None:
    """5 KPIs: Ingreso bruto · Laptops vendidas · Excedente total · Excedente promedio · Tasa conversión.

    La tasa de conversión se calcula sobre los datos ya filtrados (periodo/asesora),
    por lo que varía según los filtros del panel lateral.
    """
    total   = len(df_v)
    t1      = int((df_v["tipo_laptop"] == 1).sum())
    t2      = int((df_v["tipo_laptop"] == 2).sum())
    exc_tot = df_v["excedente"].sum()

    ingreso_emp = df_v["ingreso_empresa"].sum() if "ingreso_empresa" in df_v.columns else 0.0
    usa_cnt  = int((df_v["pais"] == "USA").sum())  if "pais" in df_v.columns else 0
    peru_mask = df_v["pais"] == "Peru"             if "pais" in df_v.columns else pd.Series(False, index=df_v.index)
    gan_peru  = float(df_v.loc[peru_mask, "ganancia_laptop"].sum()) if "ganancia_laptop" in df_v.columns else 0.0
    exc_peru  = float(df_v.loc[peru_mask, "excedente"].sum())
    sub_ing   = f"USA {usa_cnt}×S/350  ·  Perú gan. S/{gan_peru:,.0f} + exc. S/{exc_peru:,.0f}"

    pos     = df_v[df_v["excedente"] > 0]
    n_exc   = len(pos)
    avg_exc = pos["excedente"].mean() if n_exc > 0 else 0.0
    sub_exc = f"{n_exc} de {total} ventas generaron excedente"

    tot_v = total
    if (df_leads_filt is not None and not df_leads_filt.empty
            and "leads_revisados" in df_leads_filt.columns):
        tot_l = int(df_leads_filt["leads_revisados"].sum())
    else:
        tot_l = 0
    tasa = round(tot_v / tot_l * 100, 1) if tot_l > 0 else 0.0

    c1, c2, c3, c4, c5 = st.columns(5)
    _kpi(c1, "Ingreso bruto",      f"S/ {ingreso_emp:,.0f}", sub_ing,                              ROSA)
    _kpi(c2, "Laptops vendidas",   f"{total}",               f"T1: {t1}  ·  T2: {t2}",            AZUL)
    _kpi(c3, "Excedente total",    f"S/ {exc_tot:,.0f}",     "Suma del periodo",                   VERDE)
    _kpi(c4, "Excedente promedio", f"S/ {avg_exc:,.0f}",     sub_exc,                              NARANJA)
    _kpi(c5, "Tasa de conversión", f"{tasa:.1f}%",           f"{tot_v} ventas / {tot_l:,} leads",  VIOLETA)


# ── Gráfica 1: Mix por rango de precio ───────────────────────────────────────

def render_mix_laptops(df: pd.DataFrame) -> None:
    """Barras apiladas: laptops por 3 rangos de precio agrupadas por asesora."""
    if df.empty:
        st.warning("Sin datos.")
        return

    nombres   = ["Chelsea", "Katiuska", "Karina"]
    etiquetas = ["Chelsea (N1)", "Katiuska (N1)", "Karina (N2)"]
    RANGO_MED  = 7_000
    RANGO_ALTO = 10_000

    bandas = [
        ("< S/ 7,000",           CYAN),
        ("S/ 7,000 – S/ 10,000", VIOLETA),
        ("> S/ 10,000",          ROSA),
    ]

    def _cnt(nombre, lo, hi):
        sub = df[df["asesora"] == nombre]["precio_sugerido"]
        return int(((sub >= lo) & (sub < hi)).sum()) if hi else int((sub > lo).sum())

    conteos = [
        [_cnt(n, 0,          RANGO_MED)  for n in nombres],
        [_cnt(n, RANGO_MED,  RANGO_ALTO) for n in nombres],
        [_cnt(n, RANGO_ALTO, None)       for n in nombres],
    ]

    fig = go.Figure()
    for (label, color), vals in zip(bandas, conteos):
        fig.add_trace(go.Bar(
            name=label, x=etiquetas, y=vals,
            marker=dict(color=color, line=dict(width=0)),
            text=[str(v) if v > 0 else "" for v in vals],
            textposition="inside",
            textfont=dict(color="white", size=12),
        ))

    totales = [sum(c[i] for c in conteos) for i in range(len(nombres))]
    for lbl, tot in zip(etiquetas, totales):
        fig.add_annotation(x=lbl, y=tot, text=f"<b>{tot}</b>",
                           showarrow=False, yshift=10,
                           font=dict(size=14, color="#1E293B"))

    layout = {**_L, "legend": dict(
        orientation="h", yanchor="top", y=-0.18,
        xanchor="center", x=0.5, font=dict(size=12),
        bgcolor="rgba(0,0,0,0)", borderwidth=0,
    )}
    fig.update_layout(**layout,
                      title=dict(text="<b>Mix de laptops por rango de precio</b>",
                                 font=dict(size=14), x=0, xanchor="left"),
                      barmode="stack", bargap=0.40,
                      xaxis=dict(showgrid=False, tickfont=dict(size=13)),
                      yaxis=dict(**_G, title="Unidades"))
    with st.container():
        st.markdown(_CHART, unsafe_allow_html=True)
        st.plotly_chart(fig, width="stretch")
        st.markdown(_CHART_END, unsafe_allow_html=True)


# ── Gráfica 2: Excedente mensual + acumulado ─────────────────────────────────

def render_excedente_mensual(df: pd.DataFrame) -> None:
    if df.empty:
        st.warning("Sin datos.")
        return
    df = df.copy()
    df["mes_k"] = pd.to_datetime(df["fecha_efectiva_venta"]).dt.to_period("M").astype(str)
    df["mes_l"] = pd.to_datetime(df["fecha_efectiva_venta"]).dt.strftime("%b %Y")
    agg = (df.groupby(["mes_k", "mes_l"])["excedente"]
             .sum().reset_index().sort_values("mes_k"))
    agg["acum"] = agg["excedente"].cumsum()

    fig = go.Figure()
    fig.add_trace(go.Bar(
        name="Mensual", x=agg["mes_l"], y=agg["excedente"],
        marker=dict(color=AZUL, opacity=0.75, line=dict(width=0)),
        yaxis="y1",
        hovertemplate="<b>%{x}</b><br>S/ %{y:,.0f}<extra></extra>",
    ))
    fig.add_trace(go.Scatter(
        name="Acumulado", x=agg["mes_l"], y=agg["acum"],
        mode="lines+markers", yaxis="y2",
        line=dict(color=NARANJA, width=3),
        marker=dict(color=NARANJA, size=9, line=dict(color="white", width=2)),
        hovertemplate="<b>%{x}</b><br>Acum. S/ %{y:,.0f}<extra></extra>",
    ))
    fig.update_layout(**_L, title="<b>Excedente mensual y acumulado</b>",
                      xaxis=dict(showgrid=False, tickfont=dict(size=11)),
                      yaxis=dict(**_G, title="S/ mensual"),
                      yaxis2=dict(title="S/ acumulado", overlaying="y", side="right",
                                  showgrid=False, tickfont=dict(size=11)),
                      bargap=0.3)
    with st.container():
        st.markdown(_CHART, unsafe_allow_html=True)
        st.plotly_chart(fig, width="stretch")
        st.markdown(_CHART_END, unsafe_allow_html=True)


# ── Gráfica 3: Ventas mensuales por asesora ──────────────────────────────────

def render_ventas_semanales(df: pd.DataFrame) -> None:
    """Barras agrupadas por mes — comparación entre asesoras."""
    if df.empty:
        st.warning("Sin datos.")
        return
    df = df.copy()
    df["mes_k"] = pd.to_datetime(df["fecha_efectiva_venta"]).dt.to_period("M").astype(str)
    df["mes_l"] = pd.to_datetime(df["fecha_efectiva_venta"]).dt.strftime("%b %Y")
    meses_k     = sorted(df["mes_k"].unique())
    mes_map     = {r["mes_k"]: r["mes_l"]
                   for _, r in df[["mes_k", "mes_l"]].drop_duplicates().iterrows()}

    fig = go.Figure()
    for nombre, color in [("Chelsea", C_CHELSEA), ("Katiuska", C_KATIUSKA), ("Karina", C_KARINA)]:
        sub = df[df["asesora"] == nombre]
        cnt = sub.groupby("mes_k").size().reindex(meses_k, fill_value=0)
        fig.add_trace(go.Bar(
            name=nombre, x=[mes_map[m] for m in meses_k], y=cnt.values,
            marker=dict(color=color, line=dict(width=0)),
            text=cnt.values, textposition="outside",
            textfont=dict(size=11, color=color),
            hovertemplate=f"<b>{nombre}</b><br>%{{x}}<br><b>%{{y}} ventas</b><extra></extra>",
        ))

    fig.update_layout(**_L,
                      title=dict(text="<b>Ventas mensuales por asesora</b>",
                                 font=dict(size=14), x=0, xanchor="left"),
                      barmode="group", bargap=0.22, bargroupgap=0.08,
                      xaxis=dict(showgrid=False, tickfont=dict(size=12)),
                      yaxis=dict(**_G, title="Ventas", rangemode="tozero"))
    with st.container():
        st.markdown(_CHART, unsafe_allow_html=True)
        st.plotly_chart(fig, width="stretch")
        st.markdown(_CHART_END, unsafe_allow_html=True)


# ── Gráfica 4: Ingreso bruto mensual por asesora ─────────────────────────────

def render_ingreso_mensual(df: pd.DataFrame) -> None:
    """Barras agrupadas: ingreso bruto mensual por asesora (USA S/350 · Perú ganancia+exc)."""
    if df.empty:
        st.warning("Sin datos.")
        return
    df = df.copy()
    col_ingreso = "ingreso_empresa" if "ingreso_empresa" in df.columns else "excedente"
    df["mes_k"] = pd.to_datetime(df["fecha_efectiva_venta"]).dt.to_period("M").astype(str)
    df["mes_l"] = pd.to_datetime(df["fecha_efectiva_venta"]).dt.strftime("%b %Y")
    meses_k     = sorted(df["mes_k"].unique())
    mes_map     = {r["mes_k"]: r["mes_l"]
                   for _, r in df[["mes_k", "mes_l"]].drop_duplicates().iterrows()}

    fig = go.Figure()
    for nombre, color in [("Chelsea", C_CHELSEA), ("Katiuska", C_KATIUSKA), ("Karina", C_KARINA)]:
        sub = df[df["asesora"] == nombre]
        agg = sub.groupby("mes_k")[col_ingreso].sum().reindex(meses_k, fill_value=0).reset_index()
        agg["lbl"] = agg["mes_k"].map(mes_map)
        fig.add_trace(go.Bar(
            name=nombre, x=agg["lbl"], y=agg[col_ingreso],
            marker=dict(color=color, line=dict(width=0)),
            text=agg[col_ingreso].map(lambda v: f"S/{v:,.0f}"),
            textposition="outside",
            textfont=dict(size=10, color=color),
            hovertemplate=f"<b>{nombre}</b><br>%{{x}}<br>S/ %{{y:,.0f}}<extra></extra>",
        ))

    fig.update_layout(**_L, title="<b>Ingreso bruto mensual por asesora</b>",
                      barmode="group", bargap=0.22, bargroupgap=0.07,
                      xaxis=dict(showgrid=False, tickfont=dict(size=11)),
                      yaxis=dict(**_G, title="S/ ingreso bruto"))
    with st.container():
        st.markdown(_CHART, unsafe_allow_html=True)
        st.plotly_chart(fig, width="stretch")
        st.markdown(_CHART_END, unsafe_allow_html=True)


# ── Gráfica 5: Leads revisados por hora ──────────────────────────────────────

def render_leads_hora_bar(pivot: pd.DataFrame) -> None:
    """Barras agrupadas: leads revisados por hora del día."""
    if pivot.empty:
        st.warning("Sin datos de horario.")
        return

    horas = list(range(6, 24))
    etiq  = [f"{h:02d}:00" for h in horas]

    fig = go.Figure()
    fig.add_vrect(x0="10:00", x1="19:00",
                  fillcolor="#F0FDF4", opacity=0.55, layer="below", line_width=0,
                  annotation_text="Horario laboral",
                  annotation_position="top left",
                  annotation_font=dict(size=9, color="#6B7280"))

    for nombre, color in [("Chelsea", C_CHELSEA), ("Katiuska", C_KATIUSKA), ("Karina", C_KARINA)]:
        vals = [int(pivot.loc[h, nombre]) if nombre in pivot.columns else 0 for h in horas]
        fig.add_trace(go.Bar(
            name=nombre, x=etiq, y=vals,
            marker=dict(color=color, line=dict(width=0)),
            hovertemplate=f"<b>{nombre}</b><br>%{{x}}<br>%{{y}} leads revisados<extra></extra>",
        ))

    fig.update_layout(
        **{**_L, "margin": dict(t=72, b=60, l=52, r=44)},
        title=dict(text="<b>Leads revisados por hora del día</b>",
                   font=dict(size=14), x=0, xanchor="left"),
        barmode="group", bargap=0.18, bargroupgap=0.06,
        xaxis=dict(showgrid=False, tickfont=dict(size=9), tickangle=45, title="Hora del día"),
        yaxis=dict(**_G, title="Leads revisados"),
    )
    with st.container():
        st.markdown(_CHART, unsafe_allow_html=True)
        st.plotly_chart(fig, width="stretch")
        st.markdown(_CHART_END, unsafe_allow_html=True)


# ── Gráfica 6: Leads asignados (donut) ───────────────────────────────────────

def render_leads_asignados_pie(df_res: pd.DataFrame) -> None:
    """Donut chart: distribución de leads asignados por asesora."""
    if df_res.empty:
        st.warning("Sin datos.")
        return

    asesoras = df_res["asesora"].tolist()
    valores  = df_res["leads_asignados"].tolist()
    colors   = [COLOR_ASESORA.get(a, AZUL) for a in asesoras]

    fig = go.Figure(go.Pie(
        labels=asesoras, values=valores,
        marker=dict(colors=colors, line=dict(color="white", width=2)),
        textinfo="label+percent+value",
        textfont=dict(size=12, color="white"),
        hovertemplate="<b>%{label}</b><br>%{value:,} leads asignados<br>%{percent}<extra></extra>",
        hole=0.38,
    ))
    fig.update_layout(
        **{**_L, "margin": dict(t=72, b=70, l=20, r=20),
           "legend": dict(orientation="h", yanchor="bottom", y=-0.22,
                          xanchor="center", x=0.5, font=dict(size=11))},
        title=dict(text="<b>Leads asignados por asesora</b>",
                   font=dict(size=14), x=0, xanchor="left"),
    )
    with st.container():
        st.markdown(_CHART, unsafe_allow_html=True)
        st.plotly_chart(fig, width="stretch")
        st.markdown(_CHART_END, unsafe_allow_html=True)


# ── Tabla resumen ─────────────────────────────────────────────────────────────

def render_tabla_resumen(df_res: pd.DataFrame,
                          df_v: pd.DataFrame | None = None,
                          subtitulo: str = "Periodo 19 mar → hoy") -> None:
    """
    Tabla única por asesora: ventas (ingreso bruto, excedente, Perú/USA, tasa de
    conversión) + atención de leads (asignados, revisados, tasa de revisión,
    hora pico) + expander con desglose Perú.
    """
    if df_res.empty:
        st.warning("Sin datos de resumen.")
        return
    st.markdown(f'<div class="section-lbl">Resumen por asesora · {subtitulo}</div>',
                unsafe_allow_html=True)

    cols = ["asesora", "ingreso_bruto", "excedente_total",
            "peru", "usa", "ventas_total",
            "leads_asignados", "leads_revisados", "tasa_revision",
            "tasa_conversion", "hora_pico"]
    out = df_res[[c for c in cols if c in df_res.columns]].copy()

    for col in ["ingreso_bruto", "excedente_total"]:
        if col in out.columns:
            out[col] = out[col].map(lambda x: f"S/ {x:,.2f}")
    for col in ["tasa_conversion", "tasa_revision"]:
        if col in out.columns:
            out[col] = out[col].map(lambda x: f"{x:.1f}%" if pd.notna(x) else "—")
    for col in ["leads_asignados", "leads_revisados"]:
        if col in out.columns:
            out[col] = out[col].map(lambda x: f"{int(x):,}" if pd.notna(x) else "—")
    if "hora_pico" in out.columns:
        out["hora_pico"] = out["hora_pico"].map(
            lambda x: f"{int(x):02d}:00" if pd.notna(x) else "—"
        )

    out.rename(columns={
        "asesora":         "Asesora",
        "ingreso_bruto":   "Ingreso bruto",
        "excedente_total": "Excedente total",
        "peru":            "Ventas Perú",
        "usa":             "Ventas USA",
        "ventas_total":    "Total ventas",
        "leads_asignados": "Leads asignados",
        "leads_revisados": "Leads revisados",
        "tasa_revision":   "Tasa revisión",
        "tasa_conversion": "Tasa conversión",
        "hora_pico":       "Hora pico",
    }, inplace=True)
    st.dataframe(out, hide_index=True, width="stretch")
    st.caption(
        "Ingreso bruto: USA=S/350 por laptop · Perú=ganancia laptop + excedente · "
        "Leads asignados/revisados excluyen ausencias de Katiuska · "
        "Tasa revisión = revisados / asignados × 100 · "
        "Tasa conversión = Total ventas / leads revisados × 100"
    )

    # Desglose Peru: ganancia laptop vs excedente
    if df_v is not None and "ganancia_laptop" in df_v.columns:
        peru_v = df_v[df_v["pais"] == "Peru"].copy()
        if not peru_v.empty:
            with st.expander("Desglose ingreso Perú — ganancia laptop vs excedente"):
                agg = (
                    peru_v.groupby("asesora")
                    .agg(
                        laptops=("ganancia_laptop", "count"),
                        ganancia_laptop=("ganancia_laptop", "sum"),
                        excedente=("excedente", "sum"),
                    )
                    .reset_index()
                )
                agg["total"] = agg["ganancia_laptop"] + agg["excedente"]
                for c in ["ganancia_laptop", "excedente", "total"]:
                    agg[c] = agg[c].map(lambda x: f"S/ {x:,.0f}")
                agg.columns = ["Asesora", "Laptops Perú",
                               "Ganancia laptop (precio − costo)",
                               "Excedente (cobrado − precio)",
                               "Total ingreso Perú"]
                st.dataframe(agg, hide_index=True, width="stretch")
                st.caption(
                    "Ganancia laptop = precio_laptop − r6 · "
                    "r6 incluye USD×1.18×(tc+0.05) + S/20 envío + S/50 comisión → "
                    "ganancia_laptop ya es neto para Porlles."
                )


# ── Error display ─────────────────────────────────────────────────────────────

def show_error(titulo: str, exc: Exception) -> None:
    st.error(f"**{titulo}**: {exc}")
    with st.expander("Detalle técnico"):
        import traceback
        st.code(traceback.format_exc())
