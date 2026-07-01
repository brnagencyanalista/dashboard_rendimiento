"""
dashboard.py — Punto de entrada del dashboard · Porlles Laptops
================================================================
Solo orquestación: carga de datos (cacheada), filtros y llamadas a componentes.
La lógica de negocio vive en transforms.py y en los módulos ETL.
"""

import streamlit as st
import pandas as pd

import etl_ventas
import etl_whaticket
from transforms import agregar_ganancia_laptop, construir_resumen_meses
from components import (
    CSS,
    render_kpis,
    render_mix_laptops, render_ventas_semanales,
    render_excedente_mensual, render_ingreso_mensual,
    render_leads_hora_bar, render_leads_asignados_pie,
    render_tabla_resumen, show_error,
)
from config import ASESORA_OPTS, ASESORA_MAP

# ── Carga con caché ───────────────────────────────────────────────────────────
# Streamlit invalida el caché automáticamente cuando cambia el código de la función.

@st.cache_data(show_spinner="Cargando ventas…")
def _cargar_ventas(b: bytes) -> pd.DataFrame:
    return etl_ventas.get_ventas_df(b)


@st.cache_data(show_spinner="Cargando leads…")
def _cargar_leads(b: bytes) -> pd.DataFrame:
    return etl_whaticket.get_leads_df(b)


@st.cache_data(show_spinner="Cargando pivot horario…")
def _cargar_pivot_hora(b_what: bytes) -> pd.DataFrame:
    return etl_whaticket.get_pivot_hora_asesora(b_what)


@st.cache_data(show_spinner="Calculando resumen de atención…")
def _cargar_resumen_atencion(b_what: bytes) -> pd.DataFrame:
    return etl_whaticket.get_resumen_asesoras(b_what)


# ── Filtros ───────────────────────────────────────────────────────────────────

def _filtrar(df_v: pd.DataFrame, df_l: pd.DataFrame,
             fi, ff, asesora: str | None):
    mv    = (df_v["fecha_efectiva_venta"] >= fi) & (df_v["fecha_efectiva_venta"] <= ff)
    comp  = df_v[mv].copy()
    filt  = comp[comp["asesora"] == asesora].copy() if asesora else comp.copy()

    ml    = (df_l["fecha"] >= fi) & (df_l["fecha"] <= ff)
    lfilt = df_l[ml].copy()
    if asesora:
        lfilt = lfilt[lfilt["asesora"] == asesora].copy()
    return comp, filt, lfilt


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    st.set_page_config(
        page_title="Dashboard Ventas — Porlles",
        layout="wide",
        page_icon="💻",
    )
    st.markdown(CSS, unsafe_allow_html=True)

    # ── Sidebar: uploads ──────────────────────────────────────────────────────
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

    b_lap  = f_lap.read()
    b_what = f_what.read()

    # ── Cargar datos (cacheado) ───────────────────────────────────────────────
    try:
        df_v = _cargar_ventas(b_lap)
    except Exception as e:
        show_error("Error cargando ventas", e)
        return

    try:
        df_l = _cargar_leads(b_what)
    except Exception as e:
        show_error("Error cargando leads", e)
        return

    # ── Sidebar: parámetros y filtros ─────────────────────────────────────────
    with st.sidebar:
        st.markdown("---")
        st.markdown("### Tipo de cambio")
        tc = st.number_input(
            "S/ por USD", min_value=3.0, max_value=5.5, value=3.70, step=0.01,
            help="Usado para calcular la ganancia del precio laptop (Perú)",
        )
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

    # ── Transforms: métricas derivadas ───────────────────────────────────────
    df_v = agregar_ganancia_laptop(df_v, tc)

    # ── Filtrar ───────────────────────────────────────────────────────────────
    df_comp, df_filt, df_lfilt = _filtrar(df_v, df_l, fi, ff, ase)

    if df_filt.empty and df_lfilt.empty:
        st.warning("Sin datos para los filtros seleccionados.")
        return

    # ── KPIs ─────────────────────────────────────────────────────────────────
    # La tasa de conversión usa los leads ya filtrados → varía con los filtros.
    render_kpis(df_filt, df_lfilt)
    st.markdown("<br>", unsafe_allow_html=True)

    # ── Sección 1: Volumen de ventas ──────────────────────────────────────────
    st.markdown('<div class="section-lbl">Volumen de ventas</div>', unsafe_allow_html=True)
    col1, col2 = st.columns(2, gap="large")
    with col1:
        render_mix_laptops(df_comp)
    with col2:
        render_ventas_semanales(df_comp)

    # ── Sección 2: Rentabilidad y comisiones ──────────────────────────────────
    st.markdown('<div class="section-lbl">Rentabilidad y comisiones</div>',
                unsafe_allow_html=True)
    col3, col4 = st.columns(2, gap="large")
    with col3:
        render_excedente_mensual(df_filt)
    with col4:
        render_ingreso_mensual(df_filt)

    # ── Sección 3: Atención de leads ──────────────────────────────────────────
    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown('<div class="section-lbl">Atención de leads</div>', unsafe_allow_html=True)
    try:
        pivot_hora  = _cargar_pivot_hora(b_what)
        df_atencion = _cargar_resumen_atencion(b_what)
        col5, col6  = st.columns(2, gap="large")
        with col5:
            render_leads_hora_bar(pivot_hora)
        with col6:
            render_leads_asignados_pie(df_atencion)

        if not df_atencion.empty:
            with st.expander("Ver resumen de atención por asesora"):
                out = df_atencion.copy()
                out["tasa_revision"] = out["tasa_revision"].map(
                    lambda x: f"{x:.1f}%" if pd.notna(x) else "—"
                )
                out["hora_pico"] = out["hora_pico"].map(
                    lambda x: f"{int(x):02d}:00" if pd.notna(x) else "—"
                )
                out.columns = ["Asesora", "Leads asignados", "Leads revisados",
                               "Tasa revisión", "Hora pico"]
                st.dataframe(out, hide_index=True, width="stretch")
                st.caption(
                    "Revisado = firstSentMessageAt no nulo · "
                    "Leads asignados y revisados excluyen ausencias de Katiuska"
                )
    except Exception as e:
        show_error("Error en análisis de atención", e)

    # ── Tabla resumen (abril · mayo · junio) ──────────────────────────────────
    st.markdown("<br>", unsafe_allow_html=True)
    try:
        df_res_meses = construir_resumen_meses(df_v, df_l, meses=(4, 5, 6))
        df_v_meses = df_v[
            pd.to_datetime(df_v["fecha_efectiva_venta"]).dt.month.isin([4, 5, 6])
        ]
        render_tabla_resumen(df_res_meses, df_v=df_v_meses,
                             subtitulo="Periodo abril → junio")
    except Exception as e:
        show_error("Error en tabla resumen", e)


if __name__ == "__main__":
    main()
