# Prompt para Claude Code — Porlles: Motor de Costo, Precio y Margen Unificado

## Contexto de negocio

Porlles es una unidad de venta e importación de laptops con **3 canales de abastecimiento**, cada uno con su propia lógica de costo y de precio sugerido. Ya reconstruí y validé en Python (al 100%, contra datos reales del Google Sheet "Calculadora_2026.xlsx") la lógica de **costo** y de **precio sugerido / ingreso** de los 3 canales. Lo que falta es **unificarlos en un solo motor de margen** y exponerlos en un pipeline de datos + dashboard.

Adjunto el archivo `porlles_pricing.py` con todo lo ya construido y validado. **Lee ese archivo primero**, no reescribas su lógica desde cero.

---

## Lo que ya está construido y validado (en `porlles_pricing.py`)

### Canal 1 — Deltron / Ingram / Intcomex (mayorista local, precio sin IGV)
```python
precio_sugerido_deltron(precio_sin_igv: float, tc: float, envio: float = 20.0) -> int
```
- Costo base: `R6 = precio_sin_igv * 1.18 * (tc + 0.05) + envio + 50`
- Margen: `MAX(250, R6 * 0.08)`, con ajuste de redondeo "psicológico" (bloques de 100)
- **Validado: 8/8** casos reales (rango $289–$4750)

### Canal 2 — Alcosto (mayorista local, precio ya incluye IGV)
```python
precio_sugerido_alcosto(precio_al_costo: float, tc: float, envio: float = 20.0) -> int
```
- Costo base: `R13 = precio_al_costo * (tc + 0.05) + envio + 50` (sin el factor 1.18, ya incluye IGV)
- Margen: `MAX(400, R13 * 0.09)`
- **Validado: 3/3** casos reales

### Canal 3 — Importación directa desde USA (Amazon, Costco, Microcenter, Dell, Walmart...)
```python
calc_tax(tienda: str, precio: float, tax_free_fl: bool = False) -> float
cobro_adicional(tienda: str, precio: float, is_pickup: bool, costo_extra: float) -> int
costo_laptop_usa(precio_usd, tienda, tc, *, canal="courier"|"viajero", is_pickup=False,
                  costo_envio_extra=0.0, tax_free_fl=False, peso_lb=5.0) -> dict
```
- Cadena: `precio_usd -> +tax tienda -> +cobro logístico tienda -> +costo aduana (courier o viajero)`
- Dos sub-canales con costo distinto: **courier** (DHL/FedEx, aduana completa: Ad Valorem 4% + IGV 16% + IPM 2%) vs **viajero** (encomienda, tarifa fija por tramo de valor)
- **Validado al centavo** contra un caso real completo (hoja SOFIA: Microcenter Florida, $999, tc=3.41)
- ⚠️ **Pendiente de definir**: este canal NO tiene una función de "precio sugerido" automática como Deltron/Alcosto. En el Excel original, el precio de venta lo decide la asesora manualmente, y existe una fórmula de **comisión** (no de margen) que compara `Precio de venta final` vs `Costo Final Sugerido`:
  ```
  comisión = SI(precio_venta > costo + 0.01, 0, costo_fijo + (precio_venta - costo) * %)
  ```
  Necesitamos decidir si para este canal el "ingreso" a usar en el modelo de margen es: (a) el precio de venta real que ingresó la asesora, o (b) generar una función de precio sugerido nueva con una regla de margen mínimo análoga a Deltron/Alcosto. **Pregúntame esto antes de asumir una de las dos.**

### Tabla resumen de inputs/outputs por canal

| Canal | Input clave | Output "costo" | Output "ingreso/precio sugerido" | Función |
|---|---|---|---|---|
| Deltron | precio sin IGV (USD) | R6 (antes de margen) | `precio_sugerido_deltron()` | ✅ lista |
| Alcosto | precio con IGV (USD) | R13 (antes de margen) | `precio_sugerido_alcosto()` | ✅ lista |
| USA Courier | precio tienda (USD) + tienda | `costo_laptop_usa(..., canal="courier")["costo_total_pen"]` | ❌ no existe — ver pendiente arriba | parcial |
| USA Viajero | precio tienda (USD) + tienda | `costo_laptop_usa(..., canal="viajero")["costo_total_pen"]` | ❌ no existe — ver pendiente arriba | parcial |

---

## Objetivo de esta tarea

Construir un **motor de margen unificado** que, dado un registro de venta (cualquier canal), calcule: costo total, ingreso/precio sugerido, margen absoluto y margen %. Y exponerlo en un pipeline reproducible + dashboard ejecutivo.

## Arquitectura propuesta (ajustar si encuentras algo mejor, pero justifica el cambio)

```
porlles-margen/
├── src/
│   ├── pricing/
│   │   ├── __init__.py
│   │   ├── deltron_alcosto.py      # mover precio_sugerido_deltron/alcosto desde porlles_pricing.py
│   │   ├── import_usa.py            # mover calc_tax/cobro_adicional/costo_laptop_usa
│   │   └── margen.py                # NUEVO: función unificada calcular_margen(venta: dict) -> dict
│   ├── data/
│   │   ├── google_sheets.py         # lector de las hojas (gspread o export CSV) -> DataFrames normalizados
│   │   └── schema.py                # esquema/validación de columnas esperadas por hoja
│   └── dashboard/
│       └── app.py                    # Streamlit: KPIs de margen por canal, por asesora, por fecha
├── tests/
│   └── test_pricing.py               # portar los 11 casos reales ya validados como pytest
├── requirements.txt
├── README.md
└── .env.example                      # credenciales Google Sheets (NUNCA hardcodear)
```

## Tareas concretas, en orden

1. **Reorganiza** `porlles_pricing.py` en los módulos de `src/pricing/` sin cambiar la lógica interna (son funciones ya validadas, no las reescribas).
2. **Crea `margen.py`** con `calcular_margen(venta: dict) -> dict` que:
   - Reciba un dict con al menos: `canal` (`"deltron"|"alcosto"|"usa_courier"|"usa_viajero"`), `costo_base_usd`, `tc`, y los parámetros propios de cada canal (`tienda`, `envio`, etc. según corresponda).
   - Devuelva: `costo_pen`, `ingreso_pen`, `margen_absoluto`, `margen_pct`, y el detalle intermedio (no solo el número final — necesitamos auditar cada paso en el dashboard).
   - Lance un error claro si el canal no existe o si faltan parámetros requeridos para ese canal.
3. **Escribe los tests** en `tests/test_pricing.py` portando los 11 casos reales validados (Deltron + Alcosto) y el caso de Sofia (USA courier + viajero) como aserciones `pytest`. Esto es la red de seguridad — cualquier cambio futuro a la lógica de pricing debe seguir pasando estos tests.
4. **Lector de datos** (`google_sheets.py`): debe poder leer las hojas de asesoras (Karina, Maryory, Chelsea, Katiuska, SOFIA, joselyn courier, joselyn express), `Proveedores` y `Datos Aduanas`, y devolver un DataFrame normalizado con una fila por venta y columnas consistentes entre hojas (los nombres de columna varían poco entre asesoras, pero hay que validarlo). Usa `gspread` + service account si hay credenciales disponibles; si no, acepta también la ruta a un `.xlsx` exportado como fallback para desarrollo local.
5. **Dashboard en Streamlit** (`app.py`) con como mínimo:
   - Margen total y margen % promedio, filtrable por canal y por asesora
   - Comparación de margen real (Excel) vs margen calculado (este motor) — debe coincidir, es la validación en producción
   - Gráfico de margen % distribuido por canal (para detectar qué canal es más rentable)
6. **No tomes decisiones de negocio sin preguntar**: si encuentras un caso ambiguo (como el pendiente del canal USA arriba), pregúntame explícitamente antes de implementar una solución por defecto.

## Stack técnico

- Python 3.11+, pandas, pytest
- Streamlit para el dashboard (no Dash ni Flask)
- `gspread` + `google-auth` para leer Google Sheets directamente (evitar depender de exports manuales a `.xlsx`)
- Sin frameworks de ORM/DB por ahora — los datos viven en Sheets, no hay base de datos todavía (si lo necesitamos, lo definimos en una siguiente fase)

## Criterio de aceptación

- `pytest` en verde con los 11+ casos reales ya validados
- El dashboard corre localmente con `streamlit run src/dashboard/app.py` sin errores
- El margen calculado por el motor coincide (±S/1) con el margen real observado en al menos 3 ventas de cada canal disponible en el Excel
