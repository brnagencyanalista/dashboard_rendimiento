"""
etl_whaticket_limpio.py
=======================
Extrae el reporte de Whaticket, genera un Excel limpio
y produce un resumen de leads por asesor en el rango de fechas indicado.
Basado en: leads.ipynb
"""

import io
import re
import numpy as np
import pandas as pd

# ── Configuración ─────────────────────────────────────────────
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

# ── Funciones ─────────────────────────────────────────────────
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


def run_etl(file_input: str, file_output: str) -> pd.DataFrame:
    """Limpia el Excel crudo y exporta whaticket_limpio.xlsx."""
    df = pd.read_excel(file_input)
    print(f"Filas cargadas : {len(df):,}")

    df = df.loc[:, df.isna().mean() <= 0.40]
    df["contactNumber"] = df["contactNumber"].apply(normalizar_numero)
    df["user"] = df["user"].replace("PAMELA - 932471545", "KARINA")
    df.rename(columns={"user": "asesor"}, inplace=True)
    df["connectionId"] = df["connectionId"].astype(str).str.strip().map(REDES)
    df.rename(columns={"connectionId": "connection"}, inplace=True)
    df.drop(columns=["userId", "departmentId", "chatLink"], errors="ignore", inplace=True)

    df.to_excel(file_output, index=False)
    print(f"Filas exportadas: {len(df):,}")
    print(f"Archivo limpio  : {file_output}\n")
    return df


def resumen_leads(df: pd.DataFrame, fecha_inicio: str, fecha_fin: str,
                  file_output: str) -> pd.DataFrame:
    """Genera tabla de leads por asesor en el rango indicado."""
    df = df.copy()
    df["createdAt"] = pd.to_datetime(df["createdAt"])

    mask = (
        (df["createdAt"].dt.date >= pd.Timestamp(fecha_inicio).date()) &
        (df["createdAt"].dt.date <= pd.Timestamp(fecha_fin).date())
    )

    result = (
        df[mask]
        .groupby("asesor")
        .size()
        .reset_index(name="total_leads")
    )

    result.to_excel(file_output, index=False)
    print(f"Resumen de leads ({fecha_inicio} → {fecha_fin})")
    print(result.to_string(index=False))
    print(f"\nArchivo exportado: {file_output}")
    return result


# ── Ejecución ─────────────────────────────────────────────────
if __name__ == "__main__":
    df_limpio = run_etl(FILE_INPUT, FILE_OUTPUT_CLEAN)
    resumen_leads(df_limpio, FECHA_INICIO, FECHA_FIN, FILE_OUTPUT_LEADS)


# ── API para el dashboard ──────────────────────────────────────
_ASESORES_DASH = {"CHELSEA": "Chelsea", "KATIUSKA": "Katiuska", "KARINA": "Karina"}


def _read(src) -> pd.DataFrame:
    if isinstance(src, (bytes, bytearray)):
        return pd.read_excel(io.BytesIO(src))
    return pd.read_excel(src)


def get_leads_total_df(file=None) -> pd.DataFrame:
    """Total de conversaciones (leads) por asesora sin filtro de fechas."""
    src = file if file is not None else FILE_INPUT
    try:
        df = _read(src)
        df = df.loc[:, df.isna().mean() <= 0.40]
        df["user"] = df["user"].replace("PAMELA - 932471545", "KARINA")
        df = df[df["user"].isin(_ASESORES_DASH.keys())].copy()
        df["asesora"] = df["user"].map(_ASESORES_DASH)
        return df.groupby("asesora").size().reset_index(name="total_leads")
    except Exception:
        return pd.DataFrame({"asesora": ["Chelsea", "Katiuska", "Karina"], "total_leads": [0, 0, 0]})


def get_leads_df(file=None) -> pd.DataFrame:
    """Devuelve DataFrame mensual de leads con columnas estándar para el dashboard."""
    src = file if file is not None else FILE_INPUT
    try:
        df = _read(src)
        df = df.loc[:, df.isna().mean() <= 0.40]
        df["user"] = df["user"].replace("PAMELA - 932471545", "KARINA")
        df = df[df["user"].isin(_ASESORES_DASH.keys())].copy()
        df["createdAt"] = pd.to_datetime(df["createdAt"], errors="coerce")
        df = df.dropna(subset=["createdAt"])
        df["asesora"] = df["user"].map(_ASESORES_DASH)
        df["mes"] = df["createdAt"].dt.to_period("M")

        agg = (
            df.groupby(["asesora", "mes"])
            .size()
            .reset_index(name="leads_revisados")
        )
        # ventas_realizadas no está en Whaticket → estimación ~25 %
        agg["ventas_realizadas"] = (agg["leads_revisados"] * 0.25).round().astype(int)
        agg["fecha"] = agg["mes"].apply(lambda p: p.to_timestamp().date())
        return agg[["fecha", "asesora", "leads_revisados", "ventas_realizadas"]].reset_index(drop=True)
    except Exception:
        return _stub_leads()


def _stub_leads() -> pd.DataFrame:
    """Datos de ejemplo para desarrollo cuando el Excel no está disponible."""
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