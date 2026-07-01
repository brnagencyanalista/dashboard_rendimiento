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


def construir_resumen_meses(df_v: pd.DataFrame,
                            df_l: pd.DataFrame,
                            meses: tuple[int, ...] = (4, 5, 6)) -> pd.DataFrame:
    """
    Resumen por asesora restringido a un conjunto de meses (por defecto abr-may-jun).

    Se construye directamente desde el detalle de ventas (df_v, ya con
    ingreso_empresa/ganancia_laptop) y el detalle de leads revisados por mes
    (df_l), de modo que refleja exactamente el periodo pedido.

    Entrada:
      df_v : output de etl_ventas.get_ventas_df() + agregar_ganancia_laptop()
      df_l : output de etl_whaticket.get_leads_df()
    """
    if df_v.empty:
        return pd.DataFrame()

    v = df_v.copy()
    mes_v = pd.to_datetime(v["fecha_efectiva_venta"]).dt.month
    v = v[mes_v.isin(meses)]
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
        l = df_l.copy()
        mes_l = pd.to_datetime(l["fecha"]).dt.month
        l = l[mes_l.isin(meses)]
        leads = l.groupby("asesora")["leads_revisados"].sum().rename("total_leads")
        res = res.merge(leads, on="asesora", how="left")
    else:
        res["total_leads"] = 0

    res["total_leads"] = res["total_leads"].fillna(0).astype(int)
    res["tasa_conversion"] = (
        res["ventas_total"] / res["total_leads"].replace(0, pd.NA) * 100
    ).round(1)
    return res.sort_values("ingreso_bruto", ascending=False).reset_index(drop=True)
