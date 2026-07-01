"""
transforms.py — Métricas derivadas de negocio
===============================================
Transforma DataFrames ya limpios (output del ETL) en métricas calculadas.
No lee archivos ni renderiza UI.

Reglas de negocio aquí:
  - Ganancia laptop: USA=S/350 fijo, Peru=precio_laptop − r6 (Deltron/Alcosto)
  - Comisión asesora: N1→S/50-80 + 15% exc / N2→S/60-90 + 20% exc
"""

from __future__ import annotations
import numpy as np
import pandas as pd

from config import (
    PROVEEDORES_DELTRON,
    ASESOR_NIVEL,
    COMISION_N1, COMISION_N2,
    COMISION_EXC_N1, COMISION_EXC_N2,
)

try:
    from porlles_pricing import costo_deltron, costo_alcosto
    _PRICING_OK = True
except ImportError:
    _PRICING_OK = False


# ── Ganancia laptop ───────────────────────────────────────────────────────────

def agregar_ganancia_laptop(df: pd.DataFrame, tc: float) -> pd.DataFrame:
    """
    Agrega columna 'ganancia_laptop' al DataFrame de ventas.

    Fórmula por pais:
      USA  : S/350 fijo (margen por importación directa)
      Peru : precio_laptop − r6/r13
             Deltron → r6  = USD × 1.18 × (tc + 0.05) + 20 + 50
             Alcosto → r13 = USD        × (tc + 0.05) + 20 + 50
             Los S/20 (envío) y S/50 (comisión asesora) ya están dentro
             del costo, por lo que ganancia_laptop ya es neto para Porlles.

    También actualiza 'ingreso_empresa' para Peru a ganancia_laptop + excedente.
    """
    df = df.copy()
    df["ganancia_laptop"] = np.nan

    # USA: margen fijo
    usa = df["pais"] == "USA"
    df.loc[usa, "ganancia_laptop"] = 350.0

    if not _PRICING_OK or "precio_usd_costo" not in df.columns:
        return df

    peru = (df["pais"] == "Peru") & (df["precio_usd_costo"] > 0)
    if not peru.any():
        return df

    usd   = df.loc[peru, "precio_usd_costo"]
    prov  = df.loc[peru, "proveedor"].astype(str).str.strip().str.upper()
    ps    = df.loc[peru, "precio_sugerido"]

    es_deltron = prov.isin(PROVEEDORES_DELTRON)
    r_deltron  = usd * 1.18 * (tc + 0.05) + 20 + 50
    r_alcosto  = usd          * (tc + 0.05) + 20 + 50
    costo_pen  = np.where(es_deltron, r_deltron, r_alcosto)

    df.loc[peru, "ganancia_laptop"] = (ps.values - costo_pen).round(2)

    # Recalcular ingreso_empresa con la ganancia real
    df.loc[peru, "ingreso_empresa"] = (
        df.loc[peru, "ganancia_laptop"] + df.loc[peru, "excedente"]
    ).round(2)

    return df


# ── Comisión asesora ──────────────────────────────────────────────────────────

def calcular_comision(nivel: int, tipo: int, excedente: float) -> float:
    """
    Comisión estimada por laptop según PDF Comisiones 2026.
      Nivel 1: T1=S/50, T2=S/80, + 15% del excedente
      Nivel 2: T1=S/60, T2=S/90, + 20% del excedente
    """
    exc    = max(0.0, float(excedente))
    base   = COMISION_N1.get(tipo, 50) if nivel == 1 else COMISION_N2.get(tipo, 60)
    pct    = COMISION_EXC_N1 if nivel == 1 else COMISION_EXC_N2
    return base + exc * pct


def agregar_comision(df: pd.DataFrame) -> pd.DataFrame:
    """Agrega columna 'comision' al DataFrame de ventas fila-por-fila."""
    df = df.copy()
    df["comision"] = [
        calcular_comision(
            int(row.get("nivel_asesora", 1)),
            int(row.get("tipo_laptop",   1)),
            float(row.get("excedente",    0)),
        )
        for _, row in df.iterrows()
    ]
    return df


# ── Resumen general (merge ventas + leads) ────────────────────────────────────

def construir_resumen_general(df_resumen: pd.DataFrame,
                               df_leads: pd.DataFrame) -> pd.DataFrame:
    """
    Combina el resumen de ventas con el total de leads y calcula tasa de conversión.
    Entrada:
      df_resumen : output de etl_ventas.get_resumen_df()
      df_leads   : output de etl_whaticket.get_leads_total_df()
    """
    if df_resumen.empty:
        return df_resumen
    df = df_resumen.merge(df_leads, on="asesora", how="left")
    df["total_leads"]     = df["total_leads"].fillna(0).astype(int)
    df["ventas_total"]    = df["peru"] + df["usa"]
    df["tasa_conversion"] = (
        df["ventas_total"] / df["total_leads"].replace(0, pd.NA) * 100
    ).round(1)
    return df.sort_values("ingreso_bruto", ascending=False).reset_index(drop=True)


def _anio_objetivo(df_v: pd.DataFrame,
                   fecha_col: str = "fecha_efectiva_venta") -> int | None:
    """Año más reciente presente en el detalle de ventas (para acotar el periodo)."""
    if df_v.empty:
        return None
    fechas = pd.to_datetime(df_v[fecha_col], errors="coerce")
    return int(fechas.dt.year.max()) if fechas.notna().any() else None


def filtrar_meses(df: pd.DataFrame,
                  meses: tuple[int, ...] = (4, 5, 6),
                  anio: int | None = None,
                  fecha_col: str = "fecha_efectiva_venta") -> pd.DataFrame:
    """
    Filtra un DataFrame a los meses indicados de un año concreto.
    Si `anio` es None, usa el año más reciente presente en la columna de fecha,
    evitando mezclar, p. ej., abril-2025 con abril-2026.
    """
    if df.empty:
        return df
    fechas = pd.to_datetime(df[fecha_col], errors="coerce")
    if not fechas.notna().any():
        return df.iloc[0:0].copy()
    if anio is None:
        anio = int(fechas.dt.year.max())
    mask = fechas.dt.year.eq(anio) & fechas.dt.month.isin(meses)
    return df[mask.fillna(False)].copy()


def construir_resumen_meses(df_v: pd.DataFrame,
                            df_l: pd.DataFrame,
                            meses: tuple[int, ...] = (4, 5, 6)) -> pd.DataFrame:
    """
    Resumen por asesora restringido a un conjunto de meses del año más reciente
    (por defecto abr-may-jun del último año presente en las ventas).

    Se construye directamente desde el detalle de ventas (df_v, ya con
    ingreso_empresa/ganancia_laptop) y el detalle de leads revisados por mes
    (df_l), de modo que refleja exactamente el periodo pedido.

    Entrada:
      df_v : output de etl_ventas.get_ventas_df() + agregar_ganancia_laptop()
      df_l : output de etl_whaticket.get_leads_df()
    """
    anio = _anio_objetivo(df_v)
    if anio is None:
        return pd.DataFrame()

    v = filtrar_meses(df_v, meses, anio, "fecha_efectiva_venta")
    if v.empty:
        return pd.DataFrame()

    res = (
        v.groupby("asesora")
        .agg(
            ingreso_bruto=("ingreso_empresa", "sum"),
            excedente_total=("excedente", "sum"),
            peru=("pais", lambda s: int((s == "Peru").sum())),
            usa=("pais",  lambda s: int((s == "USA").sum())),
        )
        .reset_index()
    )
    res["ventas_total"] = res["peru"] + res["usa"]

    if df_l is not None and not df_l.empty and "leads_revisados" in df_l.columns:
        l = filtrar_meses(df_l, meses, anio, "fecha")
        leads = l.groupby("asesora")["leads_revisados"].sum().rename("total_leads")
        res = res.merge(leads, on="asesora", how="left")
    else:
        res["total_leads"] = 0

    res["total_leads"] = res["total_leads"].fillna(0).astype(int)
    res["tasa_conversion"] = (
        res["ventas_total"] / res["total_leads"].replace(0, pd.NA) * 100
    ).round(1)
    return res.sort_values("ingreso_bruto", ascending=False).reset_index(drop=True)


def construir_resumen_completo(df_res: pd.DataFrame,
                               df_aten: pd.DataFrame) -> pd.DataFrame:
    """
    Une el resumen de ventas por asesora (ingreso bruto, excedente, ventas
    Perú/USA, tasa de conversión) con el resumen de atención de leads
    (asignados, revisados, tasa de revisión, hora pico) en una sola tabla.

    Entrada:
      df_res  : output de construir_resumen_meses()
      df_aten : output de etl_whaticket.resumen_from() para el mismo periodo
    """
    if df_res.empty:
        return df_res

    cols_aten = ["asesora", "leads_asignados", "leads_revisados",
                 "tasa_revision", "hora_pico"]
    out = df_res.copy()

    if df_aten is not None and not df_aten.empty:
        aten = df_aten[[c for c in cols_aten if c in df_aten.columns]]
        out = out.merge(aten, on="asesora", how="left")
    else:
        for c in cols_aten[1:]:
            out[c] = pd.NA

    return out.sort_values("ingreso_bruto", ascending=False).reset_index(drop=True)
