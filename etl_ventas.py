"""
etl_ventas.py — ETL de laptops (IMPORTACION + PROVEDORES)
===========================================================
Flujo de transformación:
  1. _open(src)               → ExcelFile (acepta ruta, bytes o file-like)
  2. _leer_importacion(xls)   → DataFrame crudo USA renombrado
  3. _leer_provedores(xls)    → DataFrame crudo Peru con detección flexible de columnas
  4. _normalizar_asesores(df) → limpia nombres, filtra a las 3 asesoras válidas
  5. _limpiar_numericos(df)   → convierte columnas numéricas
  6. _filtrar_fechas(df, ...) → aplica rango de fechas

API pública (usada por dashboard.py):
  get_ventas_df(file)   → DataFrame fila-por-venta
  get_resumen_df(file)  → DataFrame agregado por asesora

ETL standalone (python etl_ventas.py):
  cargar_y_limpiar(file) → usa los mismos helpers internos
  generar_resumen(df)    → tabla de resumen
"""

import io
import numpy as np
import pandas as pd

from config import (
    ASESORES_VALIDOS, ASESOR_NIVEL, ASESOR_NOMBRE,
    ASESOR_COL_CANDIDATOS,
    RENAME_IMPORTACION, RENAME_PROVEDORES, COLS_BASE,
    FECHA_INICIO, FECHA_FIN,
)

FILE_INPUT  = "LAPTOPS_EN_IMPORTACION_Y_STOCK_-_SEGUIMIENTO.xlsx"
FILE_OUTPUT = "ventas_limpio.xlsx"

_COLS_NUMERICAS = ["precio_laptop", "excedente_total", "total_cobrado", "precio_dolares"]


# ── I/O ───────────────────────────────────────────────────────────────────────

def _open(src) -> pd.ExcelFile:
    if isinstance(src, (bytes, bytearray)):
        return pd.ExcelFile(io.BytesIO(src))
    return pd.ExcelFile(src)


# ── Pasos de transformación ───────────────────────────────────────────────────

def _leer_importacion(xls: pd.ExcelFile) -> pd.DataFrame:
    """Lee hoja IMPORTACION, renombra columnas y marca pais=USA."""
    df = xls.parse("IMPORTACION").rename(columns=RENAME_IMPORTACION)
    df["pais"]      = "USA"
    df["proveedor"] = pd.NA
    return df


def _leer_provedores(xls: pd.ExcelFile) -> pd.DataFrame:
    """Lee hoja PROVEDORES con detección flexible de columna asesor y excedente."""
    df = xls.parse("PROVEDORES")

    # Detectar columna asesor (varía entre versiones del Excel)
    for cand in ASESOR_COL_CANDIDATOS:
        if cand in df.columns and cand != "asesor":
            df = df.rename(columns={cand: "asesor"})
            break

    # Detectar columna excedente (nombre varía con texto largo)
    if "excedente_total" not in df.columns:
        exc_col = next(
            (c for c in df.columns if "EXCEDENTE TOTAL" in str(c).upper()), None
        )
        if exc_col:
            df = df.rename(columns={exc_col: "excedente_total"})

    df = df.rename(columns=RENAME_PROVEDORES)
    df["pais"] = "Peru"
    return df


def _normalizar_asesores(df: pd.DataFrame) -> pd.DataFrame:
    """Normaliza nombres de asesores a mayúsculas y filtra a las 3 válidas."""
    df = df.copy()
    df["asesor"] = df["asesor"].astype(str).str.strip().str.upper()
    df["asesor"] = df["asesor"].replace({"PAMELA - 932471545": "KARINA", "-": "MARYORY"})
    return df[df["asesor"].isin(ASESORES_VALIDOS)].copy()


def _limpiar_numericos(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    for col in _COLS_NUMERICAS:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)
    return df


def _filtrar_fechas(df: pd.DataFrame,
                    inicio: pd.Timestamp,
                    fin: pd.Timestamp) -> pd.DataFrame:
    col = "fecha_pedido_venta"
    mask = (df[col] >= inicio) & (df[col] <= fin)
    return df[mask].copy()


# ── API para el dashboard ─────────────────────────────────────────────────────

def get_ventas_df(file=None) -> pd.DataFrame:
    """
    DataFrame fila-por-venta con columnas estándar para el dashboard.
    IMPORTACION = USA · PROVEDORES = Peru
    tipo_laptop: 1 si precio_laptop < 3500, 2 si ≥ 3500
    """
    src = file if file is not None else FILE_INPUT
    try:
        xls = _open(src)

        want_imp  = ["asesor", "fecha_pedido_venta", "precio_laptop", "total_cobrado",
                     "excedente_total", "lead_organico", "precio_dolares", "proveedor", "pais"]
        want_prov = ["asesor", "fecha_pedido_venta", "precio_laptop", "total_cobrado",
                     "excedente_total", "precio_dolares", "proveedor", "pais"]

        df1 = _leer_importacion(xls)
        df1 = df1[[c for c in want_imp if c in df1.columns]].copy()

        df2 = _leer_provedores(xls)
        df2 = df2[[c for c in want_prov if c in df2.columns]].copy()

        df = pd.concat([df1, df2], ignore_index=True)
        df = _normalizar_asesores(df)
        df = _limpiar_numericos(df)
        df["fecha_pedido_venta"] = pd.to_datetime(
            df["fecha_pedido_venta"], errors="coerce"
        ).dt.date

        ps   = df.get("precio_laptop",  pd.Series(0.0, index=df.index))
        exc  = df.get("excedente_total", pd.Series(0.0, index=df.index))
        usd  = df.get("precio_dolares",  pd.Series(np.nan, index=df.index))
        prov = df.get("proveedor",       pd.Series(pd.NA,  index=df.index))
        lead = (df["lead_organico"].fillna(False).astype(bool)
                if "lead_organico" in df.columns
                else pd.Series(False, index=df.index))
        pais = df.get("pais", pd.Series("USA", index=df.index))

        out = pd.DataFrame({
            "fecha_efectiva_venta": df["fecha_pedido_venta"],
            "asesora":              df["asesor"].map(ASESOR_NOMBRE),
            "precio_sugerido":      ps,
            "precio_cobrado":       df.get("total_cobrado", pd.Series(0.0, index=df.index)),
            "excedente":            exc.round(2),
            "precio_usd_costo":     usd,
            "proveedor":            prov,
            "ingreso_empresa":      pd.Series(
                                        np.where(pais == "USA", 350.0, exc.values),
                                        index=df.index
                                    ).round(2),
            "lead_organico":        lead,
            "tipo_laptop":          (ps >= 3500).astype(int) + 1,
            "nivel_asesora":        df["asesor"].map(ASESOR_NIVEL),
            "pais":                 pais,
        })
        return out.dropna(subset=["asesora", "fecha_efectiva_venta"]).reset_index(drop=True)
    except Exception as e:
        raise RuntimeError(f"get_ventas_df falló: {e}") from e


def get_resumen_df(file=None) -> pd.DataFrame:
    """
    Resumen por asesora: excedente, ingreso bruto y conteo de ventas por país.
    ingreso_bruto: USA → S/350 por laptop, Peru → excedente.
    """
    src = file if file is not None else FILE_INPUT
    try:
        xls = _open(src)

        df1 = _leer_importacion(xls)
        df1 = df1[[c for c in COLS_BASE if c in df1.columns] + ["pais"]].copy()

        df2 = _leer_provedores(xls)
        df2 = df2[[c for c in COLS_BASE if c in df2.columns] + ["pais"]].copy()

        df = pd.concat([df1, df2], ignore_index=True)
        df = _normalizar_asesores(df)
        df = _limpiar_numericos(df)
        df["fecha_pedido_venta"] = pd.to_datetime(df["fecha_pedido_venta"], errors="coerce")
        df = _filtrar_fechas(df, FECHA_INICIO, pd.Timestamp.today().normalize())

        df["ingreso_bruto"] = np.where(
            df["pais"] == "USA",
            350.0,
            df["excedente_total"].fillna(0),
        )

        resumen = (
            df.groupby("asesor")[["excedente_total", "ingreso_bruto"]]
            .sum().reset_index()
        )
        ventas_pais = (
            df.pivot_table(index="asesor", columns="pais",
                           values="total_cobrado", aggfunc="count", fill_value=0)
            .reset_index()
        )
        resultado = resumen.merge(ventas_pais, on="asesor", how="left")
        for col in ["Peru", "USA"]:
            if col not in resultado.columns:
                resultado[col] = 0
        resultado.rename(columns={"Peru": "peru", "USA": "usa"}, inplace=True)
        resultado["asesora"] = resultado["asesor"].map(ASESOR_NOMBRE)
        return resultado[["asesora", "excedente_total", "ingreso_bruto", "peru", "usa"]]
    except Exception as e:
        raise RuntimeError(f"get_resumen_df falló: {e}") from e


# ── ETL standalone ────────────────────────────────────────────────────────────

def cargar_y_limpiar(file_input: str = FILE_INPUT) -> pd.DataFrame:
    """Carga y limpia ambas hojas; devuelve DataFrame unificado."""
    xls = _open(file_input)

    df1 = _leer_importacion(xls)
    df2 = _leer_provedores(xls)

    for df in [df1, df2]:
        df["fecha_pedido_venta"] = pd.to_datetime(
            df["fecha_pedido_venta"], errors="coerce"
        ).dt.normalize()

    df1 = df1[[c for c in COLS_BASE + ["pais"] if c in df1.columns]].copy()
    df2 = df2[[c for c in COLS_BASE + ["pais"] if c in df2.columns]].copy()

    df = pd.concat([df1, df2], ignore_index=True)
    df = _normalizar_asesores(df)
    df = _limpiar_numericos(df)
    df = _filtrar_fechas(df, FECHA_INICIO, FECHA_FIN)

    print(f"Registros cargados: {len(df):,}")
    return df


def generar_resumen(df: pd.DataFrame) -> pd.DataFrame:
    """Resumen de totales y conteo de ventas por país."""
    resumen = (
        df.groupby("asesor")[["total_cobrado", "precio_laptop", "excedente_total"]]
        .sum().reset_index()
    )
    ventas_pais = (
        df.pivot_table(index="asesor", columns="pais",
                       values="total_cobrado", aggfunc="count", fill_value=0)
        .reset_index()
    )
    resultado = resumen.merge(ventas_pais, on="asesor", how="left")
    resultado.rename(columns={"Peru": "ventas_peru", "USA": "ventas_usa"}, inplace=True)
    return resultado


if __name__ == "__main__":
    df = cargar_y_limpiar()
    resumen = generar_resumen(df)
    print("\nResumen por asesor:")
    print(resumen.to_string(index=False))
    with pd.ExcelWriter(FILE_OUTPUT, engine="openpyxl") as writer:
        df.to_excel(writer, sheet_name="ventas_detalle", index=False)
        resumen.to_excel(writer, sheet_name="resumen_asesores", index=False)
    print(f"\nArchivo exportado: {FILE_OUTPUT}")
