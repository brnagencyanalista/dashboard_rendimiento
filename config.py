"""
config.py — Configuración centralizada · Porlles Laptops
=========================================================
Modifica aquí fechas, asesoras, colores y umbrales.
Ningún otro módulo debe definir estas constantes.
"""
import pandas as pd

# ── Período de análisis ───────────────────────────────────────────────────────
FECHA_INICIO = pd.Timestamp("2026-03-19")
FECHA_FIN    = pd.Timestamp("2026-06-19")   # usado en ETL standalone

# ── Asesoras ──────────────────────────────────────────────────────────────────
ASESORES_VALIDOS  = {"KARINA", "CHELSEA", "KATIUSKA"}
ASESOR_NIVEL      = {"CHELSEA": 1, "KATIUSKA": 1, "KARINA": 2}
ASESOR_NOMBRE     = {"CHELSEA": "Chelsea", "KATIUSKA": "Katiuska", "KARINA": "Karina"}

# Nombres posibles de la columna asesor en PROVEDORES (el Excel varía entre versiones)
ASESOR_COL_CANDIDATOS = ["Asesores", "Asesora", "ASESORES", "ASESORA", "asesor", "ASESOR"]

# ── Ausencias Katiuska ────────────────────────────────────────────────────────
# Joselyn usó su cuenta en estas fechas → leads NO reflejan rendimiento de Katiuska.
KATIUSKA_AUSENCIAS = [
    (pd.Timestamp("2026-04-09"), pd.Timestamp("2026-04-25 23:59:59")),  # descanso médico
    (pd.Timestamp("2026-04-27"), pd.Timestamp("2026-04-29 23:59:59")),  # vacaciones adelantadas
]

# ── Whaticket: IDs de conexión → red social ───────────────────────────────────
REDES = {
    "79384cf2-114c-4ad5-85d8-876f8fd6b4c6": "WhatsApp",
    "12a435fd-e3ee-4ac9-a2f5-e6cae2cf2981": "Facebook",
    "72673b80-1fc9-438c-9de7-380c4a30bd46": "Tiktok",
    "e27d6740-5304-44ff-b405-1ffc7e67be9d": "Instagram",
}

# ── Proveedores Peru: tipo de fórmula de precio ───────────────────────────────
# Deltron/Ingram/Intcomex → precio SIN IGV → fórmula aplica ×1.18
# Cualquier otro proveedor → precio CON IGV → sin factor ×1.18
PROVEEDORES_DELTRON = {"DELTRON", "INGRAM", "INTCOMEX", "INGRAM MICRO"}

# ── Mapeo de columnas Excel → nombres internos ────────────────────────────────
RENAME_IMPORTACION = {
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

RENAME_PROVEDORES = {
    "Asesores":                                                         "asesor",
    "PROVEEDOR":                                                        "proveedor",
    "FECHA DE PEDIDO / VENTA":                                          "fecha_pedido_venta",
    "SN":                                                               "sn",
    "Nombre Laptop":                                                    "nombre_laptop",
    "NOMBRE DEL CLIENTE":                                               "nombre_cliente",
    "COMISIÓN PARA EL MES":                                             "comision_laptop",
    "COMISIÓN VALIDADA":                                                "comision_validada",
    "¿Comprobante emitido?":                                            "comprobante_emitido",
    "CORREO ELECTRONICO":                                               "correo_electronico",
    "NUMERO DE CELULAR":                                                "numero_celular",
    "ADELANTO":                                                         "adelanto",
    "TOTAL COBRADO":                                                    "total_cobrado",
    "PRECIO DE SOLO LAPTOP":                                            "precio_laptop",
    "Precio en dolares":                                                "precio_dolares",
    "EXCEDENTE TOTAL ( hasta la el 15/10/2025 iba todo a fixit)":       "excedente_total",
    "EXCEDENTE PARA PORLLES":                                           "excedente_porlles",
    "LICENCIAS / SERVICIOS":                                            "licencias_servicios",
    "Accesorios costo":                                                 "accesorios_adicionales",
    "Accesorios regalo/venta":                                          "accesorios_regalo",
}

# Columnas mínimas usadas en el resumen agregado
COLS_BASE = ["asesor", "fecha_pedido_venta", "total_cobrado",
             "precio_laptop", "precio_dolares", "excedente_total"]

# ── Comisiones asesoras (PDF Comisiones 2026) ─────────────────────────────────
COMISION_N1 = {1: 50, 2: 80}   # nivel 1: tipo1 → S/50, tipo2 → S/80
COMISION_N2 = {1: 60, 2: 90}   # nivel 2: tipo1 → S/60, tipo2 → S/90
COMISION_EXC_N1 = 0.15          # % del excedente para nivel 1
COMISION_EXC_N2 = 0.20          # % del excedente para nivel 2

# Umbrales de nivel (ventas/mes)
UMBRAL_BAJA_INMEDIATA = 10
UMBRAL_BAJA_RIESGO    = 16
UMBRAL_SUBE_PROGRESO  = 20
UMBRAL_SUBE_INMEDIATA = 30

# ── Colores UI ────────────────────────────────────────────────────────────────
C_CHELSEA  = "#6366F1"
C_KATIUSKA = "#10B981"
C_KARINA   = "#F59E0B"

AZUL    = "#2563EB"
VERDE   = "#059669"
NARANJA = "#EA580C"
VIOLETA = "#7C3AED"
ROSA    = "#E11D48"
CYAN    = "#0891B2"

COLOR_ASESORA = {"Chelsea": C_CHELSEA, "Katiuska": C_KATIUSKA, "Karina": C_KARINA}

# ── Sidebar: selector de asesora ─────────────────────────────────────────────
ASESORA_OPTS = ["Equipo total", "Chelsea (N1)", "Katiuska (N1)", "Karina (N2)"]
ASESORA_MAP  = {
    "Equipo total":  None,
    "Chelsea (N1)":  "Chelsea",
    "Katiuska (N1)": "Katiuska",
    "Karina (N2)":   "Karina",
}
