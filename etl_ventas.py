"""
etl_ventas.py
=============
Extrae y consolida las hojas IMPORTACION y PROVEDORES del Excel de laptops,
limpia los datos y genera un resumen de ventas por asesor.
Basado en: etl_rendimiento.ipynb
"""

import io
import pandas as pd
import numpy as np

# ── Configuración ─────────────────────────────────────────────
FILE_INPUT  = "LAPTOPS_EN_IMPORTACION_Y_STOCK_-_SEGUIMIENTO.xlsx"
FILE_OUTPUT = "ventas_limpio.xlsx"

FECHA_INICIO = pd.Timestamp("2026-03-19")
FECHA_FIN    = pd.Timestamp("2026-06-19")

ASESORES_VALIDOS = ["KARINA", "CHELSEA", "KATIUSKA"]

# ── Mapeo de columnas ─────────────────────────────────────────
RENAME_DF1 = {
    "Asesora":                          "asesor",
    "FECHA DE PEDIDO / VENTA":          "fecha_pedido_venta",
    "Nombre Laptop":                    "nombre_laptop",
    "NOMBRE DEL CLIENTE":               "nombre_cliente",
    "LLEGARON / NO LLEGARON":           "llegaron_no_llegaron",
    "ORDEN DE COMPRA/ código interno":  "orden_compra",
    "NUMERO DE CELULAR":                "numero_celular",
    "Tipo de producto":                 "tipo_producto",
    "TIPO DE PAGO":                     "tipo_pago",
    "ADELANTO":                         "adelanto",
    "POR COBRAR":                       "por_cobrar",
    "TOTAL COBRADO":                    "total_cobrado",
    "PRECIO DE SOLO LAPTOP":            "precio_laptop",
    "PPRECIO EN DOLARES (EEUU)":        "precio_dolares",
    "(FÓRMULA) TOTAL EXCEDENTE":        "excedente_total",
    "(FÓRMULA)\nTOTAL EXCEDENTE NETO":  "excedente_neto",
    "LICENCIAS / SERVICIOS":            "licencias_servicios",
    "GARANTIA EXPRESS":                 "garantia_express",
    "GARANTIA \nFIXIT":                 "garantia_fixit",
    "Accesorios adicionales":           "accesorios_adicionales",
    "Accesorios regalo":                "accesorios_regalo",
    "LLENÓ EL FORM":                    "lleno_form",
    "¿Comprobante emitido?":            "comprobante_emitido",
    "CORREO ELECTRONICO ":              "correo_electronico",
    "ADJUNTO DNI":                      "adjunto_dni",
    "OBSERVACION":                      "observacion",
    "ENVIO":                            "envio",
    "DEPARTAMENTO":                     "departamento",
    "ESTADO DEL PAQUETE":               "estado_paquete",
    "MES PEDIDO":                       "mes_pedido",
    "COMISIÓN PARA LAPTOP":             "comision_laptop",
    "COMISIÓN VALIDADA":                "comision_validada",
    "COMISIÓN PARA EXCEDENTES":         "comision_excedentes",
    "LEAD ORGÁNICO":                    "lead_organico",
    "T&C":                              "tyc",
}

RENAME_DF2 = {
    "Asesores":                                                          "asesor",
    "PROVEEDOR":                                                         "proveedor",
    "FECHA DE PEDIDO / VENTA":                                           "fecha_pedido_venta",
    "SN":                                                                "sn",
    "Nombre Laptop":                                                     "nombre_laptop",
    "NOMBRE DEL CLIENTE":                                                "nombre_cliente",
    "COMISIÓN PARA EL MES":                                              "comision_laptop",
    "COMISIÓN VALIDADA":                                                 "comision_validada",
    "¿Comprobante emitido?":                                             "comprobante_emitido",
    "CORREO ELECTRONICO":                                                "correo_electronico",
    "NUMERO DE CELULAR":                                                 "numero_celular",
    "ADELANTO":                                                          "adelanto",
    "TOTAL COBRADO":                                                     "total_cobrado",
    "PRECIO DE SOLO LAPTOP":                                             "precio_laptop",
    "Precio en dolares":                                                 "precio_dolares",
    "EXCEDENTE TOTAL ( hasta la el 15/10/2025 iba todo a fixit)":        "excedente_total",
    "EXCEDENTE PARA PORLLES":                                            "excedente_porlles",
    "LICENCIAS / SERVICIOS":                                             "licencias_servicios",
    "Accesorios costo":                                                  "accesorios_adicionales",
    "Accesorios regalo/venta":                                           "accesorios_regalo",
}

COLS_BASE = ["asesor", "fecha_pedido_venta", "total_cobrado",
             "precio_laptop", "precio_dolares", "excedente_total"]


# ── ETL ───────────────────────────────────────────────────────
def cargar_y_limpiar(file_input: str) -> pd.DataFrame:
    # 1. Leer hojas
    df1 = pd.read_excel(file_input, sheet_name="IMPORTACION")
    df2 = pd.read_excel(file_input, sheet_name="PROVEDORES")
    print(f"IMPORTACION : {df1.shape[0]:,} filas | PROVEDORES: {df2.shape[0]:,} filas")

    # 2. Renombrar columnas
    df1 = df1.rename(columns=RENAME_DF1)
    df2 = df2.rename(columns=RENAME_DF2)

    # 3. Seleccionar columnas base y etiquetar país
    df1 = df1[[c for c in COLS_BASE if c in df1.columns]].copy()
    df2 = df2[[c for c in COLS_BASE if c in df2.columns]].copy()
    df1["pais"] = "USA"
    df2["pais"] = "Peru"

    # 4. Parsear fechas
    for df in [df1, df2]:
        df["fecha_pedido_venta"] = pd.to_datetime(
            df["fecha_pedido_venta"], errors="coerce"
        ).dt.normalize()

    # 5. Limpiar numéricos
    for df in [df1, df2]:
        for col in ["precio_laptop", "excedente_total", "total_cobrado", "precio_dolares"]:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce").round(2)

    # 6. Filtrar por rango de fechas
    for df in [df1, df2]:
        mask = (df["fecha_pedido_venta"] >= FECHA_INICIO) & \
               (df["fecha_pedido_venta"] <= FECHA_FIN)
        df.drop(index=df[~mask].index, inplace=True)

    # 7. Unir
    df_final = pd.concat([df1, df2], ignore_index=True)

    # 8. Normalizar asesores y filtrar
    df_final["asesor"] = df_final["asesor"].replace("-", "MARYORY")
    df_final = df_final[df_final["asesor"].isin(ASESORES_VALIDOS)].copy()

    print(f"Registros tras limpieza: {len(df_final):,}")
    return df_final


def generar_resumen(df: pd.DataFrame) -> pd.DataFrame:
    """Resumen de totales + conteo de ventas por país por asesor."""
    resumen = (
        df.groupby("asesor")[["total_cobrado", "precio_laptop", "excedente_total"]]
        .sum()
        .reset_index()
    )

    ventas_pais = (
        df.pivot_table(
            index="asesor",
            columns="pais",
            values="total_cobrado",
            aggfunc="count",
            fill_value=0,
        )
        .reset_index()
    )

    resultado = resumen.merge(ventas_pais, on="asesor", how="left")
    resultado.rename(columns={"Peru": "ventas_peru", "USA": "ventas_usa"}, inplace=True)
    return resultado


# ── Ejecución ─────────────────────────────────────────────────
if __name__ == "__main__":
    df = cargar_y_limpiar(FILE_INPUT)

    resumen = generar_resumen(df)
    print("\nResumen por asesor:")
    print(resumen.to_string(index=False))

    with pd.ExcelWriter(FILE_OUTPUT, engine="openpyxl") as writer:
        df.to_excel(writer, sheet_name="ventas_detalle", index=False)
        resumen.to_excel(writer, sheet_name="resumen_asesores", index=False)

    print(f"\nArchivo exportado: {FILE_OUTPUT}")


# ── API para el dashboard ──────────────────────────────────────
_NIVEL   = {"CHELSEA": 1, "KATIUSKA": 1, "KARINA": 2}
_NOMBRE  = {"CHELSEA": "Chelsea", "KATIUSKA": "Katiuska", "KARINA": "Karina"}


def _open(src) -> pd.ExcelFile:
    """Acepta ruta, bytes o file-like object y devuelve ExcelFile."""
    if isinstance(src, (bytes, bytearray)):
        return pd.ExcelFile(io.BytesIO(src))
    return pd.ExcelFile(src)


# Posibles nombres de la columna asesor en PROVEDORES
_ASESOR_CANDIDATES = ["Asesores", "Asesora", "ASESORES", "ASESORA", "asesor", "ASESOR"]


def _parse_provedores(xls: pd.ExcelFile) -> pd.DataFrame:
    """Lee PROVEDORES con detección flexible de la columna asesor y excedente."""
    df = xls.parse("PROVEDORES")

    # 1. Detectar y normalizar columna asesor
    for cand in _ASESOR_CANDIDATES:
        if cand in df.columns and cand != "asesor":
            df = df.rename(columns={cand: "asesor"})
            break

    # 2. Detectar columna excedente (el nombre puede tener texto variable)
    if "excedente_total" not in df.columns:
        exc_col = next(
            (c for c in df.columns if "EXCEDENTE TOTAL" in str(c).upper()), None
        )
        if exc_col:
            df = df.rename(columns={exc_col: "excedente_total"})

    # 3. Aplicar rename estándar para el resto de columnas
    df = df.rename(columns=RENAME_DF2)
    return df


def get_resumen_df(file=None) -> pd.DataFrame:
    """Resumen por asesora: totales + conteo ventas por país (IMPORTACION=USA, PROVEDORES=Peru).
    Filtra desde FECHA_INICIO hasta hoy."""
    src = file if file is not None else FILE_INPUT
    try:
        xls = _open(src)

        df1 = xls.parse("IMPORTACION").rename(columns=RENAME_DF1)
        df1 = df1[[c for c in COLS_BASE if c in df1.columns]].copy()
        df1["pais"] = "USA"

        df2 = _parse_provedores(xls)
        df2 = df2[[c for c in COLS_BASE if c in df2.columns]].copy()
        df2["pais"] = "Peru"

        df = pd.concat([df1, df2], ignore_index=True)
        df["asesor"] = df["asesor"].astype(str).str.strip().str.upper()
        df["asesor"] = df["asesor"].replace("PAMELA - 932471545", "KARINA")
        df = df[df["asesor"].isin(ASESORES_VALIDOS)].copy()

        df["fecha_pedido_venta"] = pd.to_datetime(df["fecha_pedido_venta"], errors="coerce")
        hoy  = pd.Timestamp.today().normalize()
        mask = (df["fecha_pedido_venta"] >= FECHA_INICIO) & (df["fecha_pedido_venta"] <= hoy)
        df   = df[mask].copy()

        for col in ["precio_laptop", "excedente_total", "total_cobrado"]:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)

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
        for col in ["Peru", "USA"]:
            if col not in resultado.columns:
                resultado[col] = 0
        resultado.rename(columns={"Peru": "peru", "USA": "usa"}, inplace=True)
        resultado["asesora"] = resultado["asesor"].map(_NOMBRE)
        return resultado[["asesora", "total_cobrado", "precio_laptop", "excedente_total", "peru", "usa"]]
    except Exception as e:
        raise RuntimeError(f"get_resumen_df falló: {e}") from e


def get_ventas_df(file=None) -> pd.DataFrame:
    """Devuelve DataFrame fila-por-venta para el dashboard.
    IMPORTACION = USA · PROVEDORES = Peru.
    tipo_laptop se determina por precio_laptop (< 3500 → tipo 1, ≥ 3500 → tipo 2)."""
    src = file if file is not None else FILE_INPUT
    try:
        xls = _open(src)

        df1 = xls.parse("IMPORTACION").rename(columns=RENAME_DF1)
        want1 = ["asesor", "fecha_pedido_venta", "precio_laptop",
                 "total_cobrado", "excedente_total", "lead_organico"]
        df1 = df1[[c for c in want1 if c in df1.columns]].copy()
        df1["pais"] = "USA"

        df2 = _parse_provedores(xls)
        want2 = ["asesor", "fecha_pedido_venta", "precio_laptop",
                 "total_cobrado", "excedente_total"]
        df2 = df2[[c for c in want2 if c in df2.columns]].copy()
        df2["pais"] = "Peru"

        df = pd.concat([df1, df2], ignore_index=True)

        # Normalizar asesor a mayúsculas
        df["asesor"] = df["asesor"].astype(str).str.strip().str.upper()
        df["asesor"] = df["asesor"].replace("PAMELA - 932471545", "KARINA")
        df = df[df["asesor"].isin(ASESORES_VALIDOS)].reset_index(drop=True)

        df["fecha_pedido_venta"] = pd.to_datetime(
            df["fecha_pedido_venta"], errors="coerce"
        ).dt.date

        for col in ["precio_laptop", "total_cobrado", "excedente_total"]:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)

        ps      = df["precio_laptop"] if "precio_laptop" in df.columns else pd.Series(0.0, index=df.index)
        exc     = df["excedente_total"] if "excedente_total" in df.columns else pd.Series(0.0, index=df.index)
        lead    = (df["lead_organico"].fillna(False).astype(bool)
                   if "lead_organico" in df.columns
                   else pd.Series(False, index=df.index))
        pais    = df["pais"] if "pais" in df.columns else pd.Series("USA", index=df.index)

        out = pd.DataFrame({
            "fecha_efectiva_venta": df["fecha_pedido_venta"],
            "asesora":              df["asesor"].map(_NOMBRE),
            "precio_sugerido":      ps,
            "precio_cobrado":       df.get("total_cobrado", pd.Series(0.0, index=df.index)),
            "excedente":            exc.round(2),
            "lead_organico":        lead,
            "tipo_laptop":          (ps >= 3500).astype(int) + 1,
            "nivel_asesora":        df["asesor"].map(_NIVEL),
            "pais":                 pais,
        })
        return out.dropna(subset=["asesora", "fecha_efectiva_venta"]).reset_index(drop=True)
    except Exception as e:
        raise RuntimeError(f"get_ventas_df falló: {e}") from e


def _stub_ventas() -> pd.DataFrame:
    """Datos de ejemplo para desarrollo cuando el Excel no está disponible."""
    rng = np.random.default_rng(42)
    precios = [2200.0, 2500.0, 2800.0, 3200.0, 3500.0, 3800.0, 4200.0, 4800.0]
    excedentes = [0.0, 0.0, 0.0, 100.0, 150.0, 200.0, 250.0, 300.0, 400.0]
    asesoras = [("Chelsea", 1), ("Katiuska", 1), ("Karina", 2)]
    rows = []
    for asesora, nivel in asesoras:
        for _ in range(int(rng.integers(20, 30))):
            ps = float(rng.choice(precios))
            ex = float(rng.choice(excedentes))
            rows.append({
                "fecha_efectiva_venta": (
                    pd.Timestamp("2026-03-19") + pd.Timedelta(days=int(rng.integers(0, 91)))
                ).date(),
                "asesora":         asesora,
                "precio_sugerido": ps,
                "precio_cobrado":  ps + ex,
                "excedente":       ex,
                "lead_organico":   bool(rng.integers(0, 2)),
                "tipo_laptop":     1 if ps < 3500 else 2,
                "nivel_asesora":   nivel,
            })
    return pd.DataFrame(rows).sort_values("fecha_efectiva_venta").reset_index(drop=True)