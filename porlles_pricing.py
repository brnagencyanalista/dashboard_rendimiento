"""
Porlles · Calculadoras de precio sugerido y costos de importación
===================================================================

Traducción 1:1 a Python del Apps Script real (compartido por el usuario),
NO una reconstrucción por ingeniería inversa. Validado contra 11 casos
reales extraídos de Calculadora_2026.xlsx: 11/11 coincidencias exactas
(ver bloque __main__).

Funciones incluidas:
- precio_sugerido_deltron   : laptops comprados a Deltron/Ingram/Intcomex (mayoristas en Perú, precio sin IGV)
- precio_sugerido_alcosto   : laptops "al costo" (precio ya incluye IGV)
- calc_tax                  : impuesto de venta en tiendas USA (con tax-holiday Florida)
- cobro_adicional           : cobro de servicio logístico por tienda (Dell, Walmart, Costco Miami/NY, Microcenter NY/Duluth/Florida)
- get_import_price          : calculadora general de importación (función "params" — variante más nueva, NO la usada en las hojas de asesoras)
- aplicar_a_dataframe       : helper para correr cualquiera de las calculadoras sobre un catálogo completo en batch
"""

from __future__ import annotations
import math
import pandas as pd


# ---------------------------------------------------------------------------
# 1) DELTRON / INGRAM / INTCOMEX
# ---------------------------------------------------------------------------
def precio_sugerido_deltron(precio_sin_igv: float, tc: float, envio: float = 20.0) -> int:
    """
    R6 = precio_sin_igv * 1.18 * (tc + 0.05) + envio + 50
    S6 = R6 + MAX(250, R6 * 0.08)

    Si precio_sin_igv > 250: ajuste por bloques de 100 sobre S6
        residuo < 30  -> base - 1
        residuo 30-69 -> base + 50
        residuo >= 70 -> base + 99
    Si precio_sin_igv <= 250: redondeo al múltiplo de 5 más cercano,
        margen = MAX(9, R6 * 0.25)
    """
    r6 = precio_sin_igv * 1.18 * (tc + 0.05) + envio + 50
    s6 = r6 + max(250.0, r6 * 0.08)

    if precio_sin_igv > 250:
        m = s6 % 100
        base = s6 - m
        if m < 30:
            precio = base - 1
        elif m < 70:
            precio = base + 50
        else:
            precio = base + 99
    else:
        ajuste = max(9.0, r6 * 0.25)
        precio = round((r6 + ajuste) / 5) * 5

    return int(round(precio))


# ---------------------------------------------------------------------------
# 2) ALCOSTO (precio ya incluye IGV — proveedor local distinto a Deltron)
# ---------------------------------------------------------------------------
def precio_sugerido_alcosto(precio_al_costo: float, tc: float, envio: float = 20.0) -> int:
    """
    R13 = precio_al_costo * (tc + 0.05) + envio + 50      <- sin el factor 1.18 (ya incluye IGV)
    S13 = R13 + MAX(400, R13 * 0.09)

    Mismas reglas de bloques de 100 / redondeo a 5 que Deltron.
    """
    r13 = precio_al_costo * (tc + 0.05) + envio + 50
    s13 = r13 + max(400.0, r13 * 0.09)

    if precio_al_costo > 250:
        m = s13 % 100
        base = s13 - m
        if m < 30:
            precio = base - 1
        elif m < 70:
            precio = base + 50
        else:
            precio = base + 99
    else:
        ajuste = max(9.0, r13 * 0.25)
        precio = round((r13 + ajuste) / 5) * 5

    return int(round(precio))


# ---------------------------------------------------------------------------
# 3) Impuesto de venta en tienda USA (con tax-holiday Florida)
# ---------------------------------------------------------------------------
_TIENDAS_FLORIDA_ELEGIBLES = {"amazon", "ebay", "bestbuy", "wallmart", "costco miami", "costco ny"}
BASE_TAX_RATE = 0.07


def calc_tax(tienda: str, precio: float, tax_free_fl: bool = False) -> float:
    """Impuesto de venta (USD, 2 decimales). Exonera 0% en FL si tax_free_fl=True, tienda elegible y precio < 1500."""
    p = float(precio)
    if not math.isfinite(p) or p <= 0:
        return 0.0

    tienda_lc = (tienda or "").strip().lower()
    rate = BASE_TAX_RATE
    if tax_free_fl and tienda_lc in _TIENDAS_FLORIDA_ELEGIBLES and p < 1500:
        rate = 0.0

    return round(p * rate, 2)


# ---------------------------------------------------------------------------
# 4) Cobro adicional (servicio logístico) por tienda
# ---------------------------------------------------------------------------
def cobro_adicional(tienda: str, precio: float, is_pickup: bool, costo_extra: float) -> int:
    """Cobro adicional de servicio según tienda de origen en USA. Replica COBRO_ADICIONAL de Apps Script."""
    t = (tienda or "").strip().lower()
    precio_aux = float(precio) if precio not in (None, "") else 0.0
    membresia_costco = 25.0

    cobro = 0.0
    pickup = 50.0 if is_pickup else 0.0

    if t in ("dell", "wallmart"):
        costo_por_comprar = 40.0
        costo_global = precio_aux * 1.2 / 100 + 5
        ganancia_extra = 20.0
        cobro = costo_por_comprar + costo_global + ganancia_extra

    elif t == "costco miami":
        costo_por_comprar = 20.0 if is_pickup else 40.0
        taxes_envio = 0.0 if is_pickup else 15 * 0.07
        pago_viajera = membresia_costco + costo_por_comprar + taxes_envio
        costo_global = precio_aux * 1.5 / 100 + 5
        ganancia_extra = 30.0
        cobro = pago_viajera + costo_global + ganancia_extra

    elif t == "costco ny":
        costo_por_comprar = 10.0 if is_pickup else 40.0
        taxes_envio = 0.0 if is_pickup else 15 * 0.07
        pago_viajera = membresia_costco + costo_por_comprar + taxes_envio
        taxes_extra = 1.875 * precio_aux / 100
        costo_global = precio_aux * 0.01 + 5
        ganancia_extra = 20.0
        envio_fedex = 140.0
        cobro = pago_viajera + taxes_extra + costo_global + ganancia_extra + envio_fedex

    elif t == "microcenter ny":
        taxes_extra = 1.875 * precio_aux / 100
        costo_emergencia = 20.0
        pickup = 0.0  # ya incluido
        cobro = 70 + 140 + taxes_extra + costo_emergencia

    elif t == "microcenter duluth":
        cobro_por_laptop = 10.0  # 16'':170, 18'':200 (ver nota original)
        pickup = 0.0
        cobro = 60 + 50 + cobro_por_laptop

    elif t == "microcenter florida":
        pickup = 0.0
        cobro = 60 + 30

    total = cobro + pickup + float(costo_extra or 0)
    return math.ceil(total)


# ---------------------------------------------------------------------------
# 5) Costo de laptop importado desde USA (cadena completa: tienda -> aduana)
#    Constantes tomadas 1:1 de la hoja 'Datos Aduanas' del Excel.
# ---------------------------------------------------------------------------
DATOS_ADUANAS = {
    "PUNTO_FLETE": 7.0,       # D6 - flete por libra (canal courier)
    "PUNTO_FLETE_2": 7.5,     # D7 - flete por libra (canal viajero)
    "SERVICIO": 7.5,          # D8
    "AD_VAL": 0.04,           # D9
    "SEGURO": 0.0075,         # D10
    "IGV": 0.16,              # D11
    "IPM": 0.02,              # D12
    "PESO_DEFAULT_LB": 5.0,   # I11 (P) - peso asumido por laptop, en libras
    "EXTRA_COURIER": 30 + 50,       # I18(CCC) + I19(CCP)
    "EXTRA_VIAJERO": 30 + 80 + 15,  # I13(CCC) + I14(CCP) + I15(Dry)
}

# Tabla de tarifas por tramo (hoja 'Datos Aduanas', columnas Q:S) — canal Viajero
_TABLA_SERVICIO_VIAJERO = [
    (0, 120), (1000, 140), (1200, 155), (1500, 195), (1650, 205),
    (2000, 245), (2500, 290), (3000, 370), (4000, 470),
]


def _roundup(x: float, decimals: int = 2) -> float:
    """Replica ROUNDUP de Excel (redondeo hacia arriba, no al más cercano)."""
    factor = 10 ** decimals
    return math.ceil(x * factor - 1e-9) / factor


def _costo_servicio_courier(precio_final_tienda: float, peso_lb: float = DATOS_ADUANAS["PESO_DEFAULT_LB"]) -> float:
    """Costo de aduana/courier (DHL/FedEx). Réplica de la fórmula F22 de las hojas de asesoras."""
    d = DATOS_ADUANAS
    if precio_final_tienda < 200:
        base = peso_lb * d["PUNTO_FLETE_2"] + d["SERVICIO"]
    else:
        cif = precio_final_tienda + precio_final_tienda * d["SEGURO"] + peso_lb * d["PUNTO_FLETE"]
        base = _roundup(
            cif * d["AD_VAL"] + cif * (1 + d["AD_VAL"]) * (d["IGV"] + d["IPM"]) + peso_lb * d["PUNTO_FLETE"] + d["SERVICIO"],
            2,
        )
    return base + d["EXTRA_COURIER"]


def _costo_servicio_viajero(valor_referencia: float) -> float:
    """Costo de viajero/encomienda, por tramo de valor. Réplica de la fórmula F16 (VLOOKUP)."""
    resultado = _TABLA_SERVICIO_VIAJERO[0][1]
    for tramo, valor in _TABLA_SERVICIO_VIAJERO:
        if valor_referencia >= tramo:
            resultado = valor
        else:
            break
    return resultado + DATOS_ADUANAS["EXTRA_VIAJERO"]


def costo_laptop_usa(precio_usd: float, tienda: str, tc: float, *, canal: str = "courier",
                      is_pickup: bool = False, costo_envio_extra: float = 0.0,
                      tax_free_fl: bool = False, peso_lb: float = DATOS_ADUANAS["PESO_DEFAULT_LB"]) -> dict:
    """
    Costo completo (USD y PEN) de traer un laptop desde una tienda de USA hasta Perú.

    canal: "courier" (DHL/FedEx, más caro pero más rápido) o "viajero" (encomienda, más barato).

    Validado al centavo contra el ejemplo real de la hoja SOFIA:
    precio_usd=999, tienda='Microcenter Florida', tc=3.41, costo_envio_extra=15
        -> precio_final_tienda=1173.93, costo_servicio(courier)=399.17,
           costo_total_usd(courier)=1573.10, costo_total_pen(courier)=5364.27
           costo_servicio(viajero)=265, costo_total_usd(viajero)=1438.93, costo_total_pen(viajero)=4906.75

    Returns
    -------
    dict con el detalle de cada paso (tax, cobro_adicional, precio_final_tienda,
    costo_servicio, costo_total_usd, costo_total_pen) — útil para auditar márgenes
    en el dashboard, no solo para obtener el número final.
    """
    tax = calc_tax(tienda, precio_usd, tax_free_fl)
    precio_con_tax = precio_usd + tax
    cobro = cobro_adicional(tienda, precio_con_tax, is_pickup, costo_envio_extra)
    precio_final_tienda = precio_con_tax + cobro

    if canal == "courier":
        costo_servicio = _costo_servicio_courier(precio_final_tienda, peso_lb)
    elif canal == "viajero":
        costo_servicio = _costo_servicio_viajero(precio_con_tax + costo_envio_extra)
    else:
        raise ValueError("canal debe ser 'courier' o 'viajero'")

    costo_total_usd = precio_final_tienda + costo_servicio
    costo_total_pen = costo_total_usd * tc

    return {
        "tienda": tienda, "canal": canal, "precio_usd": precio_usd,
        "tax": round(tax, 2), "precio_con_tax": round(precio_con_tax, 2),
        "cobro_adicional": round(cobro, 2), "precio_final_tienda": round(precio_final_tienda, 2),
        "costo_servicio": round(costo_servicio, 2),
        "costo_total_usd": round(costo_total_usd, 2),
        "costo_total_pen": round(costo_total_pen, 2),
    }


# ---------------------------------------------------------------------------
# 6) Calculadora general de importación (variante "params" — getImportPrice)
# ---------------------------------------------------------------------------
def get_import_price(tc: float, precio: float, tienda: str, params: dict) -> float | None:
    """
    Traducción de getImportPrice(). `params` debe traer las claves C3, C4, C5, C6
    (equivalentes a las celdas C3:C6 de la hoja "params" en el Sheet original).

    NOTA: esta función no estaba conectada a ninguna celda activa en las hojas
    de asesoras (Karina/Maryory/etc. usan la fórmula VLOOKUP de 'Datos Aduanas'
    en su lugar) — parece una variante más nueva en desarrollo. Confirmar con
    el usuario si debe reemplazar la lógica de 'Datos Aduanas' o es un cálculo
    paralelo/experimental antes de usarla en producción.
    """
    if tc in ("", None) or precio in ("", None) or not tienda:
        return None

    tienda_lc = tienda.lower()
    precio = float(precio)
    tc = float(tc)

    if precio < 498:
        precio_inc_tax = precio * 1.07
        f6, f7, f8 = precio_inc_tax, 3, 0.15  # peso=3, ganancia=15%
        d6, d7, d8 = 7, 7.5, 7.5
        d9, d10, d11, d12 = 0.04, 0.0075, 0.16, 0.02

        adu = f7 * d7 + d8
        if f6 > 200:
            cif = f6 + f6 * d10 + f7 * d6
            adu = round((cif * d9 + cif * (1 + d9) * (d11 + d12)) * 100) / 100

        c_final = (precio_inc_tax + adu) * tc
        return c_final * (1 + f8)

    c3, c4, c5, c6 = params["C3"], params["C4"], params["C5"], params["C6"]
    t2 = math.ceil((tc + 0.1) * 100 / 5) / 20

    t6 = (precio * 1.07
          + (30 if precio > 1199 else 0)
          + 130
          - (precio * 0.07 if tienda_lc in ("amazon", "ebay") else 0)
          + (50 if tienda_lc == "costco" else 0)
          + (40 if tienda_lc == "microcenter" else 0)) * t2

    factor = c4 if tienda_lc in ("amazon", "ebay") else c3
    u6 = t6 + max(t6 * factor, c5) + c6

    residuo = u6 % 100
    if residuo < 30:
        f6 = u6 - residuo - 1
    elif residuo < 70:
        f6 = u6 - residuo + 50
    else:
        f6 = u6 - residuo + 99

    return f6


# ---------------------------------------------------------------------------
# Helper de batch para pandas
# ---------------------------------------------------------------------------
def aplicar_pricing_catalogo(df: pd.DataFrame, col_costo: str, tc: float,
                              funcion=precio_sugerido_deltron, envio: float = 20.0,
                              col_resultado: str = "precio_sugerido") -> pd.DataFrame:
    """Aplica una de las calculadoras (deltron o alcosto) a un catálogo completo."""
    df = df.copy()
    df[col_resultado] = df[col_costo].apply(lambda x: funcion(x, tc, envio))
    return df


if __name__ == "__main__":
    tc = 3.41
    deltron_cases = [
        (289.0, 1499, "Karina"), (515.0, 2399, "joselyn courier"), (705.0, 3199, "Katiuska"),
        (789.0, 3550, "joselyn express / Proveedores"), (924.0, 4150, "SOFIA"),
        (1920.0, 8550, "Chelsea"), (4398.0, 19450, "Proveedores"), (4750.0, 20999, "Maryory"),
    ]
    alcosto_cases = [
        (1339.0, 5099, "Karina ALCOSTO"), (1285.0, 4899, "Proveedores ALCOSTO"),
        (2589.0, 9850, "Proveedores ALCOSTO"),
    ]

    print("--- DELTRON ---")
    ok = sum(precio_sugerido_deltron(d, tc, 20) == real for d, real, _ in deltron_cases)
    print(f"Aciertos: {ok}/{len(deltron_cases)}")

    print("--- ALCOSTO ---")
    ok = sum(precio_sugerido_alcosto(d, tc, 20) == real for d, real, _ in alcosto_cases)
    print(f"Aciertos: {ok}/{len(alcosto_cases)}")

    print("--- COSTO LAPTOP USA (hoja SOFIA, validado al centavo) ---")
    esperado_courier = {"precio_con_tax": 1068.93, "cobro_adicional": 105.0, "precio_final_tienda": 1173.93,
                         "costo_servicio": 399.17, "costo_total_usd": 1573.10, "costo_total_pen": 5364.27}
    r_courier = costo_laptop_usa(999.0, "Microcenter Florida", tc, canal="courier", costo_envio_extra=15.0)
    ok = all(abs(r_courier[k] - v) < 0.01 for k, v in esperado_courier.items())
    print("Courier:", r_courier, "| OK" if ok else "| FAIL")

    esperado_viajero = {"costo_servicio": 265.0, "costo_total_usd": 1438.93, "costo_total_pen": 4906.75}
    r_viajero = costo_laptop_usa(999.0, "Microcenter Florida", tc, canal="viajero", costo_envio_extra=15.0)
    ok = all(abs(r_viajero[k] - v) < 0.01 for k, v in esperado_viajero.items())
    print("Viajero:", r_viajero, "| OK" if ok else "| FAIL")
