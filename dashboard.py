"""
dashboard.py — Dashboard ejecutivo de ventas · Porlles Laptops
"""

import streamlit as st
import pandas as pd
import plotly.graph_objects as go

import etl_ventas
import etl_whaticket

# ── Paleta ────────────────────────────────────────────────────
C_CHELSEA  = "#6366F1"
C_KATIUSKA = "#10B981"
C_KARINA   = "#F59E0B"

AZUL    = "#2563EB"
VERDE   = "#059669"
NARANJA = "#EA580C"
VIOLETA = "#7C3AED"
ROSA    = "#E11D48"
CYAN    = "#0891B2"

# Umbrales de nivel — PDF Comisiones 2026
UMBRAL_BAJA_INMEDIATA = 10
UMBRAL_BAJA_RIESGO    = 16
UMBRAL_SUBE_PROGRESO  = 20
UMBRAL_SUBE_INMEDIATA = 30

ASESORA_OPTS = ["Equipo total", "Chelsea (N1)", "Katiuska (N1)", "Karina (N2)"]
ASESORA_MAP  = {
    "Equipo total":  None,
    "Chelsea (N1)":  "Chelsea",
    "Katiuska (N1)": "Katiuska",
    "Karina (N2)":   "Karina",
}

# ── CSS ───────────────────────────────────────────────────────
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

# ── Plotly layout base ────────────────────────────────────────
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


# ── Carga y caché ─────────────────────────────────────────────
_V = "v3"   # incrementar si cambia la lógica del ETL para invalidar caché

@st.cache_data(show_spinner="Cargando ventas…")
def _cargar_ventas(b: bytes, _v: str = _V) -> pd.DataFrame:
    return etl_ventas.get_ventas_df(b)

@st.cache_data(show_spinner="Cargando leads…")
def _cargar_leads(b: bytes, _v: str = _V) -> pd.DataFrame:
    return etl_whaticket.get_leads_df(b)

@st.cache_data(show_spinner="Calculando resumen…")
def _cargar_resumen(b_lap: bytes, b_what: bytes, _v: str = _V) -> pd.DataFrame:
    resumen = etl_ventas.get_resumen_df(b_lap)
    leads   = etl_whaticket.get_leads_total_df(b_what)
    if resumen.empty:
        return resumen
    df = resumen.merge(leads, on="asesora", how="left")
    df["total_leads"]     = df["total_leads"].fillna(0).astype(int)
    df["ventas_total"]    = df["peru"] + df["usa"]
    df["tasa_conversion"] = (
        df["ventas_total"] / df["total_leads"].replace(0, pd.NA) * 100
    ).round(1)
    return df.sort_values("total_cobrado", ascending=False).reset_index(drop=True)


# ── Filtros ───────────────────────────────────────────────────
def _filtrar(df_v, df_l, fi, ff, asesora):
    mv = (df_v["fecha_efectiva_venta"] >= fi) & (df_v["fecha_efectiva_venta"] <= ff)
    comp = df_v[mv].copy()
    filt = comp[comp["asesora"] == asesora].copy() if asesora else comp.copy()

    ml = (df_l["fecha"] >= fi) & (df_l["fecha"] <= ff)
    lfilt = df_l[ml].copy()
    if asesora:
        lfilt = lfilt[lfilt["asesora"] == asesora].copy()
    return comp, filt, lfilt


# ── KPI cards ─────────────────────────────────────────────────
def _kpi(col, label, value, sub, accent):
    col.markdown(
        f"""<div class="kpi-card" style="--accent:{accent}">
          <div class="kpi-label">{label}</div>
          <div class="kpi-value">{value}</div>
          <div class="kpi-sub">{sub}&nbsp;</div>
        </div>""",
        unsafe_allow_html=True,
    )


def render_kpis(df_v, df_resumen) -> None:
    total   = len(df_v)
    t1      = int((df_v["tipo_laptop"] == 1).sum())
    t2      = int((df_v["tipo_laptop"] == 2).sum())
    exc_tot = df_v["excedente"].sum()
    pos     = df_v[df_v["excedente"] > 0]
    pct_exc = (pos["excedente"] / pos["precio_sugerido"] * 100).mean() if len(pos) else 0.0

    # Tasa de conversión: misma fórmula que la tabla (ventas_total / total_leads)
    if df_resumen is not None and not df_resumen.empty:
        tot_v = int(df_resumen["ventas_total"].sum())
        tot_l = int(df_resumen["total_leads"].sum())
        tasa  = round(tot_v / tot_l * 100, 1) if tot_l > 0 else 0.0
    else:
        tasa = 0.0

    c1, c2, c3, c4 = st.columns(4)
    _kpi(c1, "Laptops vendidas",     f"{total}",            f"T1: {t1}  ·  T2: {t2}",           AZUL)
    _kpi(c2, "Excedente total",      f"S/ {exc_tot:,.0f}",  "Suma del periodo",                   VERDE)
    _kpi(c3, "% Excedente promedio", f"{pct_exc:.1f}%",     "Solo ventas con excedente",          NARANJA)
    _kpi(c4, "Tasa de conversión",   f"{tasa:.1f}%",        f"{tot_v} ventas / {tot_l:,} leads",  VIOLETA)


# ── Gráfica 1: Mix por rango de precio ───────────────────────
def render_mix_laptops(df: pd.DataFrame) -> None:
    """Barras apiladas con 3 rangos de precio (precio de solo laptop):
    Tipo 1 < S/7 800  |  Tipo 2 S/7 800–S/9 000  |  Premium > S/9 000"""
    if df.empty:
        st.warning("Sin datos.")
        return

    nombres   = ["Chelsea", "Katiuska", "Karina"]
    etiquetas = ["Chelsea (N1)", "Katiuska (N1)", "Karina (N2)"]

    # Rangos basados en precio_sugerido (= precio de solo laptop del Excel)
    RANGO_MED  = 7000
    RANGO_ALTO = 10000

    bandas = [
        ("< S/ 7,000",             CYAN,    ),
        ("S/ 7,000 – S/ 10,000",   VIOLETA, ),
        ("> S/ 10,000",            ROSA,    ),
    ]

    def _cnt(nombre, lo, hi):
        sub = df[df["asesora"] == nombre]["precio_sugerido"]
        if hi is None:
            return int((sub > lo).sum())
        return int(((sub >= lo) & (sub < hi)).sum())

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

    # Total encima de cada barra
    totales = [sum(c[i] for c in conteos) for i in range(len(nombres))]
    for lbl, tot in zip(etiquetas, totales):
        fig.add_annotation(
            x=lbl, y=tot, text=f"<b>{tot}</b>",
            showarrow=False, yshift=10,
            font=dict(size=14, color="#1E293B"),
        )

    layout = {**_L}
    layout["legend"] = dict(
        orientation="h", yanchor="top", y=-0.18,
        xanchor="center", x=0.5,
        font=dict(size=12), bgcolor="rgba(0,0,0,0)", borderwidth=0,
        traceorder="normal",
    )
    fig.update_layout(
        **layout,
        title=dict(
            text="<b>Mix de laptops por rango de precio</b>",
            font=dict(size=14), x=0, xanchor="left",
        ),
        barmode="stack", bargap=0.40,
        xaxis=dict(showgrid=False, tickfont=dict(size=13)),
        yaxis=dict(**_G, title="Unidades"),
    )
    with st.container():
        st.markdown('<div class="chart-card">', unsafe_allow_html=True)
        st.plotly_chart(fig, width="stretch")
        st.markdown('</div>', unsafe_allow_html=True)


# ── Gráfica 2: Excedente mensual + acumulado ──────────────────
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
    fig.update_layout(
        **_L, title="<b>Excedente mensual y acumulado</b>",
        xaxis=dict(showgrid=False, tickfont=dict(size=11)),
        yaxis=dict(**_G, title="S/ mensual"),
        yaxis2=dict(title="S/ acumulado", overlaying="y", side="right",
                    showgrid=False, tickfont=dict(size=11)),
        bargap=0.3,
    )
    with st.container():
        st.markdown('<div class="chart-card">', unsafe_allow_html=True)
        st.plotly_chart(fig, width="stretch")
        st.markdown('</div>', unsafe_allow_html=True)


# ── Gráfica 3: Ventas mensuales por asesora ───────────────────
def render_ventas_semanales(df: pd.DataFrame) -> None:
    """Barras agrupadas por mes — comparación directa entre asesoras."""
    if df.empty:
        st.warning("Sin datos.")
        return
    df = df.copy()
    df["mes_k"] = pd.to_datetime(df["fecha_efectiva_venta"]).dt.to_period("M").astype(str)
    df["mes_l"] = pd.to_datetime(df["fecha_efectiva_venta"]).dt.strftime("%b %Y")
    meses_k     = sorted(df["mes_k"].unique())
    mes_map     = {r["mes_k"]: r["mes_l"]
                   for _, r in df[["mes_k", "mes_l"]].drop_duplicates().iterrows()}

    config = [("Chelsea", C_CHELSEA), ("Katiuska", C_KATIUSKA), ("Karina", C_KARINA)]
    fig = go.Figure()
    for nombre, color in config:
        sub = df[df["asesora"] == nombre]
        cnt = sub.groupby("mes_k").size().reindex(meses_k, fill_value=0)
        etiq = [mes_map[m] for m in meses_k]
        fig.add_trace(go.Bar(
            name=nombre, x=etiq, y=cnt.values,
            marker=dict(color=color, line=dict(width=0)),
            text=cnt.values,
            textposition="outside",
            textfont=dict(size=11, color=color),
            hovertemplate=f"<b>{nombre}</b><br>%{{x}}<br><b>%{{y}} ventas</b><extra></extra>",
        ))

    fig.update_layout(
        **_L,
        title=dict(text="<b>Ventas mensuales por asesora</b>",
                   font=dict(size=14), x=0, xanchor="left"),
        barmode="group", bargap=0.22, bargroupgap=0.08,
        xaxis=dict(showgrid=False, tickfont=dict(size=12)),
        yaxis=dict(**_G, title="Ventas", rangemode="tozero"),
    )
    with st.container():
        st.markdown('<div class="chart-card">', unsafe_allow_html=True)
        st.plotly_chart(fig, width="stretch")
        st.markdown('</div>', unsafe_allow_html=True)


# ── Gráfica 4: Comisión estimada mensual ──────────────────────
def render_comisiones(df: pd.DataFrame) -> None:
    """Comisión estimada por asesora/mes según reglas PDF Comisiones 2026.
    N1: T1=S/50, T2=S/80, exc=15% · N2: T1=S/60, T2=S/90, exc=20%."""
    if df.empty:
        st.warning("Sin datos.")
        return
    df = df.copy()

    def _com(row):
        nivel = int(row.get("nivel_asesora", 1))
        tipo  = int(row.get("tipo_laptop", 1))
        exc   = max(0.0, float(row.get("excedente", 0)))
        if nivel == 1:
            return (50 if tipo == 1 else 80) + exc * 0.15
        return (60 if tipo == 1 else 90) + exc * 0.20

    df["comision"] = df.apply(_com, axis=1)
    df["mes_k"]    = pd.to_datetime(df["fecha_efectiva_venta"]).dt.to_period("M").astype(str)
    df["mes_l"]    = pd.to_datetime(df["fecha_efectiva_venta"]).dt.strftime("%b %Y")

    meses_k = sorted(df["mes_k"].unique())
    mes_map  = {r["mes_k"]: r["mes_l"]
                for _, r in df[["mes_k", "mes_l"]].drop_duplicates().iterrows()}

    config = [("Chelsea", C_CHELSEA), ("Katiuska", C_KATIUSKA), ("Karina", C_KARINA)]
    fig = go.Figure()

    for nombre, color in config:
        sub = df[df["asesora"] == nombre]
        agg = (sub.groupby("mes_k")["comision"]
                  .sum().reindex(meses_k, fill_value=0).reset_index())
        agg["lbl"] = agg["mes_k"].map(mes_map)

        fig.add_trace(go.Bar(
            name=nombre, x=agg["lbl"], y=agg["comision"],
            marker=dict(color=color, line=dict(width=0)),
            text=agg["comision"].map(lambda v: f"S/{v:,.0f}"),
            textposition="outside",
            textfont=dict(size=10, color=color),
            hovertemplate=f"<b>{nombre}</b><br>%{{x}}<br>S/ %{{y:,.0f}}<extra></extra>",
        ))

    fig.update_layout(
        **_L, title="<b>Comisión estimada mensual por asesora</b>",
        barmode="group", bargap=0.22, bargroupgap=0.07,
        xaxis=dict(showgrid=False, tickfont=dict(size=11)),
        yaxis=dict(**_G, title="S/ comisión estimada"),
    )
    with st.container():
        st.markdown('<div class="chart-card">', unsafe_allow_html=True)
        st.plotly_chart(fig, width="stretch")
        st.markdown('</div>', unsafe_allow_html=True)


# ── Tabla resumen ─────────────────────────────────────────────
def render_tabla_resumen(df: pd.DataFrame) -> None:
    if df.empty:
        st.warning("Sin datos de resumen.")
        return
    st.markdown('<div class="section-lbl">Resumen por asesora · Periodo 19 mar → hoy</div>',
                unsafe_allow_html=True)

    out = df[["asesora", "total_cobrado", "precio_laptop", "excedente_total",
              "peru", "usa", "ventas_total", "total_leads", "tasa_conversion"]].copy()
    out["total_cobrado"]   = out["total_cobrado"].map(lambda x: f"S/ {x:,.2f}")
    out["precio_laptop"]   = out["precio_laptop"].map(lambda x: f"S/ {x:,.2f}")
    out["excedente_total"] = out["excedente_total"].map(lambda x: f"S/ {x:,.2f}")
    out["tasa_conversion"] = out["tasa_conversion"].map(
        lambda x: f"{x:.1f}%" if pd.notna(x) else "—"
    )
    out.columns = [
        "Asesora", "Total cobrado", "Precio laptop",
        "Excedente total", "Ventas Perú", "Ventas USA",
        "Total ventas", "Total leads", "Tasa conversión",
    ]
    st.dataframe(out, hide_index=True, width="stretch")
    st.caption(
        "Ventas Perú = hoja PROVEDORES · Ventas USA = hoja IMPORTACION · "
        "Tasa conversión = Total ventas / Total leads × 100"
    )


# ── Error display ─────────────────────────────────────────────
def _show_error(titulo: str, exc: Exception) -> None:
    st.error(f"**{titulo}**: {exc}")
    with st.expander("Detalle técnico"):
        import traceback
        st.code(traceback.format_exc())


# ── Main ──────────────────────────────────────────────────────
def main() -> None:
    st.set_page_config(
        page_title="Dashboard Ventas — Porlles",
        layout="wide",
        page_icon="💻",
    )
    st.markdown(CSS, unsafe_allow_html=True)

    with st.sidebar:
        st.markdown("### Archivos de datos")
        f_lap  = st.file_uploader("Excel laptops  (IMPORTACION + PROVEDORES)", type=["xlsx"])
        f_what = st.file_uploader("Excel Whaticket (conversaciones)", type=["xlsx"])

    st.title("Dashboard de Rendimiento — Porlles Laptops")

    if f_lap is None or f_what is None:
        pending = []
        if f_lap  is None: pending.append("**Excel de laptops**")
        if f_what is None: pending.append("**Excel de Whaticket**")
        st.info("Adjunta en el panel lateral: " + "  y  ".join(pending))
        return

    # Leer a bytes una vez — evita problemas de puntero con @st.cache_data
    b_lap  = f_lap.read()
    b_what = f_what.read()

    try:
        df_v = _cargar_ventas(b_lap)
    except Exception as e:
        _show_error("Error cargando ventas", e)
        return

    try:
        df_l = _cargar_leads(b_what)
    except Exception as e:
        _show_error("Error cargando leads", e)
        return

    with st.sidebar:
        st.markdown("---")
        st.markdown("### Filtros")
        fmin = df_v["fecha_efectiva_venta"].min()
        fmax = df_v["fecha_efectiva_venta"].max()
        fi   = st.date_input("Desde", value=fmin, min_value=fmin, max_value=fmax)
        ff   = st.date_input("Hasta", value=fmax, min_value=fmin, max_value=fmax)
        sel  = st.selectbox("Asesora", ASESORA_OPTS)
        ase  = ASESORA_MAP[sel]

        st.markdown("---")
        st.markdown(
            f"**{len(df_v)} ventas** cargadas\n\n"
            f"Peru: {int((df_v['pais']=='Peru').sum())}  ·  "
            f"USA: {int((df_v['pais']=='USA').sum())}"
        )

    df_comp, df_filt, df_lfilt = _filtrar(df_v, df_l, fi, ff, ase)

    if df_filt.empty and df_lfilt.empty:
        st.warning("Sin datos para los filtros seleccionados.")
        return

    # ── KPIs ──────────────────────────────────────────────────
    try:
        df_res_kpi = _cargar_resumen(b_lap, b_what)
    except Exception:
        df_res_kpi = pd.DataFrame()
    render_kpis(df_filt, df_res_kpi)
    st.markdown("<br>", unsafe_allow_html=True)

    # ── Fila 1 ────────────────────────────────────────────────
    st.markdown('<div class="section-lbl">Volumen de ventas</div>', unsafe_allow_html=True)
    col1, col2 = st.columns(2, gap="large")
    with col1:
        render_mix_laptops(df_comp)
    with col2:
        render_ventas_semanales(df_comp)

    # ── Fila 2 ────────────────────────────────────────────────
    st.markdown('<div class="section-lbl">Rentabilidad y comisiones</div>',
                unsafe_allow_html=True)
    col3, col4 = st.columns(2, gap="large")
    with col3:
        render_excedente_mensual(df_filt)
    with col4:
        render_comisiones(df_filt)

    # ── Tabla resumen ─────────────────────────────────────────
    st.markdown("<br>", unsafe_allow_html=True)
    try:
        render_tabla_resumen(_cargar_resumen(b_lap, b_what))
    except Exception as e:
        _show_error("Error en tabla resumen", e)


if __name__ == "__main__":
    main()
