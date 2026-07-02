"""
etl_whaticket.py — ETL de Whaticket (hoja "Report")
======================================================
Flujo de transformación:
  1. _read(src)                    → DataFrame crudo de la hoja Report
  2. _normalizar_usuario(df)       → PAMELA→KARINA, filtra 3 asesoras
  3. _parsear_fechas(df)           → firstSentMessageAt y createdAt como datetime
  4. _excluir_ausencias(df, col)   → quita periodos de ausencia de Katiuska
  5. _cargar_base(src)             → helper compartido que ejecuta pasos 1-4 y
                                     devuelve (df_asignados, df_revisados)

API pública (usada por dashboard.py):
  get_leads_total_df(file)         → leads revisados por asesora (total)
  get_leads_df(file)               → leads revisados por asesora/mes
  get_pivot_hora_asesora(file)     → pivot hora×asesora de revisados
  get_horas_revision_df(file)      → hora decimal por lead revisado (para KDE)
  get_resumen_asesoras(file)       → asignados, revisados, tasa, hora pico

ETL standalone (python etl_whaticket.py):
  run_etl(file_input, file_output)
  resumen_leads(df, fecha_inicio, fecha_fin, file_output)

Reglas de negocio:
  - Lead "revisado" = firstSentMessageAt no es nulo (atención humana real).
    createdAt/assignedAt son asignación automática del bot, no cuentan.
  - Ausencias de Katiuska: leads asignados Y revisados en esas fechas son de
    Joselyn usando su cuenta → excluidos de TODAS las métricas.
"""

import io
import re
import numpy as np
import pandas as pd

from config import KATIUSKA_AUSENCIAS, REDES, ASESOR_NOMBRE, FECHA_INICIO, FECHA_FIN

FILE_INPUT        = "whaticket_conversations_report.xlsx"
FILE_OUTPUT_CLEAN = "whaticket_limpio.xlsx"
FILE_OUTPUT_LEADS = "resumen_leads.xlsx"

_ASESORES_DASH = {"CHELSEA": "Chelsea", "KATIUSKA": "Katiuska", "KARINA": "Karina"}


# ── I/O ───────────────────────────────────────────────────────────────────────

def _read(src) -> pd.DataFrame:
    """Lee el Excel de Whaticket; intenta primero la hoja 'Report'."""
    raw = io.BytesIO(src) if isinstance(src, (bytes, bytearray)) else src
    try:
        return pd.read_excel(raw, sheet_name="Report")
    except Exception:
        if hasattr(raw, "seek"):
            raw.seek(0)
        return pd.read_excel(raw)


# ── Pasos de transformación ───────────────────────────────────────────────────

def _normalizar_usuario(df: pd.DataFrame) -> pd.DataFrame:
    """Mapea 'PAMELA - <num>' → 'KARINA' y filtra las 3 asesoras."""
    df = df.copy()
    df["user"] = df["user"].astype(str).str.strip()
    df.loc[df["user"].str.startswith("PAMELA", na=False), "user"] = "KARINA"
    df = df[df["user"].isin(_ASESORES_DASH.keys())].copy()
    df["asesora"] = df["user"].map(_ASESORES_DASH)
    return df


def _parsear_fechas(df: pd.DataFrame) -> pd.DataFrame:
    """Parsea firstSentMessageAt y createdAt como datetime."""
    df = df.copy()
    df["firstSentMessageAt"] = pd.to_datetime(df["firstSentMessageAt"], errors="coerce")
    df["createdAt"] = pd.to_datetime(
        df.get("createdAt", pd.Series(dtype="datetime64[ns]")), errors="coerce"
    )
    return df


def _excluir_ausencias(df: pd.DataFrame,
                        fecha_col: str = "firstSentMessageAt") -> pd.DataFrame:
    """
    Quita filas de Katiuska cuya fecha_col cae en sus periodos de ausencia.
    La columna debe estar ya parseada como datetime.
    Si la columna no existe, devuelve df sin modificar.
    """
    if df.empty or fecha_col not in df.columns:
        return df
    excluir = pd.Series(False, index=df.index)
    for inicio, fin in KATIUSKA_AUSENCIAS:
        excluir |= (
            (df["asesora"] == "Katiuska") &
            (df[fecha_col] >= inicio) &
            (df[fecha_col] <= fin)
        )
    return df[~excluir].copy()


def _cargar_base(src) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Helper compartido que ejecuta pasos 1-4 para todas las funciones de la API.

    Retorna:
      df_asig : todos los leads (excluidas ausencias por createdAt)
                → usado para contar leads ASIGNADOS a Katiuska de forma justa
      df_rev  : solo leads revisados (firstSentMessageAt no nulo)
                con ausencias excluidas → usado para métricas de revisión
    """
    df = _read(src)
    df = _normalizar_usuario(df)
    df = _parsear_fechas(df)

    df_asig = _excluir_ausencias(df, "createdAt")
    df_rev  = _excluir_ausencias(df[df["firstSentMessageAt"].notna()].copy())
    return df_asig, df_rev


# ── API para el dashboard ─────────────────────────────────────────────────────

def get_leads_total_df(file=None) -> pd.DataFrame:
    """Leads revisados (firstSentMessageAt no nulo) por asesora — total global."""
    src = file if file is not None else FILE_INPUT
    try:
        _, df_rev = _cargar_base(src)
        return df_rev.groupby("asesora").size().reset_index(name="total_leads")
    except Exception:
        return pd.DataFrame({"asesora": list(ASESOR_NOMBRE.values()),
                             "total_leads": [0, 0, 0]})


def get_leads_df(file=None) -> pd.DataFrame:
    """Leads revisados por asesora y mes — para gráficas mensuales."""
    src = file if file is not None else FILE_INPUT
    try:
        _, df_rev = _cargar_base(src)
        df_rev["mes"]   = df_rev["firstSentMessageAt"].dt.to_period("M")
        df_rev["fecha"] = df_rev["mes"].apply(lambda p: p.to_timestamp().date())
        agg = (
            df_rev.groupby(["asesora", "mes", "fecha"])
            .size()
            .reset_index(name="leads_revisados")
        )
        agg["ventas_realizadas"] = (agg["leads_revisados"] * 0.25).round().astype(int)
        return agg[["fecha", "asesora", "leads_revisados", "ventas_realizadas"]].reset_index(drop=True)
    except Exception:
        return _stub_leads()


def get_leads_base(file=None) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Detalle base de leads ya normalizado: (df_asignados, df_revisados).

    Pensado para cachearse UNA sola vez (lectura pesada) y luego filtrarse en
    memoria con filtrar_detalle() según los filtros del dashboard.
    """
    src = file if file is not None else FILE_INPUT
    return _cargar_base(src)


def filtrar_detalle(df: pd.DataFrame,
                    fecha_col: str = "firstSentMessageAt",
                    fi=None, ff=None, asesora: str | None = None) -> pd.DataFrame:
    """Filtra un detalle de leads por rango de fechas (sobre fecha_col) y asesora."""
    if df.empty:
        return df
    out = df
    if fecha_col in out.columns and (fi is not None or ff is not None):
        fechas = out[fecha_col].dt.date
        mask = pd.Series(True, index=out.index)
        if fi is not None:
            mask &= fechas >= fi
        if ff is not None:
            mask &= fechas <= ff
        out = out[mask.fillna(False)]
    if asesora:
        out = out[out["asesora"] == asesora]
    return out.copy()


def pivot_hora_from(df_rev: pd.DataFrame) -> pd.DataFrame:
    """Pivot hora×asesora desde un detalle de revisados ya filtrado."""
    if df_rev.empty:
        return pd.DataFrame()
    d = df_rev.copy()
    d["hora"] = d["firstSentMessageAt"].dt.hour
    pivot = (
        d.pivot_table(index="hora", columns="asesora", aggfunc="size", fill_value=0)
        .reindex(range(24), fill_value=0)
    )
    pivot.index.name   = "Hora"
    pivot.columns.name = None
    return pivot


def resumen_from(df_asig: pd.DataFrame, df_rev: pd.DataFrame) -> pd.DataFrame:
    """Resumen asignados/revisados/tasa/hora pico desde detalles ya filtrados."""
    if df_asig.empty and df_rev.empty:
        return pd.DataFrame()

    asignados = df_asig.groupby("asesora").size().rename("leads_asignados")
    revisados = df_rev.groupby("asesora").size().rename("leads_revisados")

    if df_rev.empty:
        hora_pico = pd.Series(dtype="float64", name="hora_pico")
    else:
        d = df_rev.copy()
        d["hora"] = d["firstSentMessageAt"].dt.hour
        hora_pico = (
            d.groupby(["asesora", "hora"]).size()
            .reset_index(name="cnt")
            .sort_values("cnt", ascending=False)
            .drop_duplicates("asesora")
            .set_index("asesora")["hora"]
            .rename("hora_pico")
        )

    res = pd.concat([asignados, revisados, hora_pico], axis=1).reset_index()
    res = res.rename(columns={"index": "asesora"})
    res["leads_asignados"] = res["leads_asignados"].fillna(0).astype(int)
    res["leads_revisados"] = res["leads_revisados"].fillna(0).astype(int)
    res["tasa_revision"] = (
        res["leads_revisados"] / res["leads_asignados"].replace(0, np.nan) * 100
    ).round(1)
    return res[["asesora", "leads_asignados", "leads_revisados",
                "tasa_revision", "hora_pico"]]


def get_pivot_hora_asesora(file=None) -> pd.DataFrame:
    """Pivot: filas=hora (0-23), columnas=asesora, valores=leads revisados (sin filtrar)."""
    try:
        _, df_rev = _cargar_base(file if file is not None else FILE_INPUT)
        return pivot_hora_from(df_rev)
    except Exception:
        return pd.DataFrame()


def get_horas_revision_df(file=None) -> pd.DataFrame:
    """Hora decimal (h + min/60 + seg/3600) de cada lead revisado — insumo para KDE."""
    src = file if file is not None else FILE_INPUT
    try:
        _, df_rev = _cargar_base(src)
        df_rev["hora_decimal"] = (
            df_rev["firstSentMessageAt"].dt.hour
            + df_rev["firstSentMessageAt"].dt.minute / 60
            + df_rev["firstSentMessageAt"].dt.second / 3600
        )
        return df_rev[["asesora", "hora_decimal"]].reset_index(drop=True)
    except Exception:
        return pd.DataFrame(columns=["asesora", "hora_decimal"])


def get_resumen_asesoras(file=None) -> pd.DataFrame:
    """Resumen: leads asignados, revisados, tasa de revisión y hora pico (sin filtrar)."""
    try:
        df_asig, df_rev = _cargar_base(file if file is not None else FILE_INPUT)
        return resumen_from(df_asig, df_rev)
    except Exception:
        return pd.DataFrame()


# ── ETL standalone ────────────────────────────────────────────────────────────

def normalizar_numero(val) -> str | None:
    """Limpia número peruano a 9 dígitos."""
    if pd.isna(val):
        return None
    s = str(val).strip()
    try:
        s = str(int(float(s)))
    except Exception:
        pass
    digits = re.sub(r"\D", "", s)
    if digits.startswith("51") and len(digits) == 11:
        digits = digits[2:]
    if len(digits) == 9 and digits.startswith("9"):
        return digits
    return None


def run_etl(file_input: str = FILE_INPUT,
            file_output: str = FILE_OUTPUT_CLEAN) -> pd.DataFrame:
    """Limpia el Excel crudo y exporta whaticket_limpio.xlsx."""
    df = pd.read_excel(file_input, sheet_name="Report")
    print(f"Filas cargadas : {len(df):,}")

    df = df.loc[:, df.isna().mean() <= 0.40]
    df["contactNumber"] = df["contactNumber"].apply(normalizar_numero)
    df = _normalizar_usuario(df)
    df.rename(columns={"asesora": "asesor"}, inplace=True)
    if "connectionId" in df.columns:
        df["connectionId"] = df["connectionId"].astype(str).str.strip().map(REDES)
        df.rename(columns={"connectionId": "connection"}, inplace=True)
    df.drop(columns=["userId", "departmentId", "chatLink"], errors="ignore", inplace=True)

    df.to_excel(file_output, index=False)
    print(f"Filas exportadas: {len(df):,}  →  {file_output}\n")
    return df


def resumen_leads(df: pd.DataFrame, fecha_inicio: str, fecha_fin: str,
                  file_output: str = FILE_OUTPUT_LEADS) -> pd.DataFrame:
    """Leads revisados en el rango de fechas (por firstSentMessageAt)."""
    df = df.copy()
    df["firstSentMessageAt"] = pd.to_datetime(df["firstSentMessageAt"], errors="coerce")
    mask = (
        df["firstSentMessageAt"].notna() &
        (df["firstSentMessageAt"].dt.date >= pd.Timestamp(fecha_inicio).date()) &
        (df["firstSentMessageAt"].dt.date <= pd.Timestamp(fecha_fin).date())
    )
    result = (
        df[mask]
        .groupby("asesor")
        .size()
        .reset_index(name="total_leads_revisados")
    )
    result.to_excel(file_output, index=False)
    print(f"Leads revisados ({fecha_inicio} → {fecha_fin})")
    print(result.to_string(index=False))
    print(f"\nArchivo exportado: {file_output}")
    return result


# ── Stub para desarrollo ──────────────────────────────────────────────────────

def _stub_leads() -> pd.DataFrame:
    rng   = np.random.default_rng(42)
    meses = pd.date_range("2026-03-01", periods=4, freq="MS").date
    rows  = []
    for mes in meses:
        for asesora in ["Chelsea", "Katiuska", "Karina"]:
            lr = int(rng.integers(60, 130))
            rows.append({
                "fecha":             mes,
                "asesora":           asesora,
                "leads_revisados":   lr,
                "ventas_realizadas": int(rng.integers(8, 25)),
            })
    return pd.DataFrame(rows)


if __name__ == "__main__":
    df_limpio = run_etl()
    resumen_leads(df_limpio, FECHA_INICIO.strftime("%Y-%m-%d"), FECHA_FIN.strftime("%Y-%m-%d"))
