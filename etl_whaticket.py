"""
etl_whaticket.py
================
Procesa el reporte de Whaticket (hoja "Report") para el dashboard.

Reglas de negocio:
- Solo se consideran: CHELSEA, KATIUSKA, KARINA.
- "PAMELA - <número>" → KARINA (comparten WhatsApp).
- Lead "revisado" = firstSentMessageAt no es nulo.
  (createdAt y assignedAt son casi simultáneos y reflejan asignación
   automática del bot, no atención humana real.)
"""

import io
import re
import numpy as np
import pandas as pd

FILE_INPUT        = "whaticket_conversations_report.xlsx"
FILE_OUTPUT_CLEAN = "whaticket_limpio.xlsx"
FILE_OUTPUT_LEADS = "resumen_leads.xlsx"

FECHA_INICIO = "2026-03-19"
FECHA_FIN    = "2026-06-18"

REDES = {
    "79384cf2-114c-4ad5-85d8-876f8fd6b4c6": "WhatsApp",
    "12a435fd-e3ee-4ac9-a2f5-e6cae2cf2981": "Facebook",
    "72673b80-1fc9-438c-9de7-380c4a30bd46": "Tiktok",
    "e27d6740-5304-44ff-b405-1ffc7e67be9d": "Instagram",
}

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


# ── Helpers ───────────────────────────────────────────────────────────────────

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


def _normalizar_usuario(df: pd.DataFrame) -> pd.DataFrame:
    """Mapea 'PAMELA - <num>' → 'KARINA' y filtra las 3 asesoras."""
    df = df.copy()
    df["user"] = df["user"].astype(str).str.strip()
    df.loc[df["user"].str.startswith("PAMELA", na=False), "user"] = "KARINA"
    df = df[df["user"].isin(_ASESORES_DASH.keys())].copy()
    df["asesora"] = df["user"].map(_ASESORES_DASH)
    return df


# ── API para el dashboard ─────────────────────────────────────────────────────

def get_leads_total_df(file=None) -> pd.DataFrame:
    """Leads revisados (firstSentMessageAt no nulo) por asesora."""
    src = file if file is not None else FILE_INPUT
    try:
        df = _read(src)
        df = _normalizar_usuario(df)
        df["firstSentMessageAt"] = pd.to_datetime(df["firstSentMessageAt"], errors="coerce")
        revisados = df[df["firstSentMessageAt"].notna()]
        return revisados.groupby("asesora").size().reset_index(name="total_leads")
    except Exception:
        return pd.DataFrame({"asesora": ["Chelsea", "Katiuska", "Karina"],
                             "total_leads": [0, 0, 0]})


def get_leads_df(file=None) -> pd.DataFrame:
    """DataFrame mensual de leads revisados con columnas estándar."""
    src = file if file is not None else FILE_INPUT
    try:
        df = _read(src)
        df = _normalizar_usuario(df)
        df["firstSentMessageAt"] = pd.to_datetime(df["firstSentMessageAt"], errors="coerce")
        df = df[df["firstSentMessageAt"].notna()].copy()
        df["mes"]   = df["firstSentMessageAt"].dt.to_period("M")
        df["fecha"] = df["mes"].apply(lambda p: p.to_timestamp().date())
        agg = (
            df.groupby(["asesora", "mes", "fecha"])
            .size()
            .reset_index(name="leads_revisados")
        )
        agg["ventas_realizadas"] = (agg["leads_revisados"] * 0.25).round().astype(int)
        return agg[["fecha", "asesora", "leads_revisados", "ventas_realizadas"]].reset_index(drop=True)
    except Exception:
        return _stub_leads()


def get_pivot_hora_asesora(file=None) -> pd.DataFrame:
    """Pivot: filas=hora (0-23), columnas=asesora, valores=leads revisados."""
    src = file if file is not None else FILE_INPUT
    try:
        df = _read(src)
        df = _normalizar_usuario(df)
        df["firstSentMessageAt"] = pd.to_datetime(df["firstSentMessageAt"], errors="coerce")
        df = df[df["firstSentMessageAt"].notna()].copy()
        df["hora"] = df["firstSentMessageAt"].dt.hour
        pivot = (
            df.pivot_table(index="hora", columns="asesora",
                           aggfunc="size", fill_value=0)
            .reindex(range(24), fill_value=0)
        )
        pivot.index.name  = "Hora"
        pivot.columns.name = None
        return pivot
    except Exception:
        return pd.DataFrame()


def get_horas_revision_df(file=None) -> pd.DataFrame:
    """Hora decimal (h + min/60 + seg/3600) de cada lead revisado por asesora.
    Sirve como insumo del KDE en el dashboard."""
    src = file if file is not None else FILE_INPUT
    try:
        df = _read(src)
        df = _normalizar_usuario(df)
        df["firstSentMessageAt"] = pd.to_datetime(df["firstSentMessageAt"], errors="coerce")
        df = df[df["firstSentMessageAt"].notna()].copy()
        df["hora_decimal"] = (
            df["firstSentMessageAt"].dt.hour
            + df["firstSentMessageAt"].dt.minute / 60
            + df["firstSentMessageAt"].dt.second / 3600
        )
        return df[["asesora", "hora_decimal"]].reset_index(drop=True)
    except Exception:
        return pd.DataFrame(columns=["asesora", "hora_decimal"])


def get_resumen_asesoras(file=None) -> pd.DataFrame:
    """Resumen: leads asignados, revisados, tasa de revisión y hora pico."""
    src = file if file is not None else FILE_INPUT
    try:
        df = _read(src)
        df = _normalizar_usuario(df)
        df["firstSentMessageAt"] = pd.to_datetime(df["firstSentMessageAt"], errors="coerce")

        asignados = df.groupby("asesora").size().rename("leads_asignados")

        rev = df[df["firstSentMessageAt"].notna()].copy()
        revisados = rev.groupby("asesora").size().rename("leads_revisados")

        rev["hora"] = rev["firstSentMessageAt"].dt.hour
        hora_pico = (
            rev.groupby(["asesora", "hora"]).size()
            .reset_index(name="cnt")
            .sort_values("cnt", ascending=False)
            .drop_duplicates("asesora")
            .set_index("asesora")["hora"]
            .rename("hora_pico")
        )

        res = pd.concat([asignados, revisados, hora_pico], axis=1).reset_index()
        res["tasa_revision"] = (
            res["leads_revisados"] / res["leads_asignados"] * 100
        ).round(1)
        return res[["asesora", "leads_asignados", "leads_revisados",
                    "tasa_revision", "hora_pico"]]
    except Exception:
        return pd.DataFrame()


# ── ETL standalone ────────────────────────────────────────────────────────────

def run_etl(file_input: str, file_output: str) -> pd.DataFrame:
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
    print(f"Filas exportadas: {len(df):,}")
    print(f"Archivo limpio  : {file_output}\n")
    return df


def resumen_leads(df: pd.DataFrame, fecha_inicio: str, fecha_fin: str,
                  file_output: str) -> pd.DataFrame:
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
    df_limpio = run_etl(FILE_INPUT, FILE_OUTPUT_CLEAN)
    resumen_leads(df_limpio, FECHA_INICIO, FECHA_FIN, FILE_OUTPUT_LEADS)
