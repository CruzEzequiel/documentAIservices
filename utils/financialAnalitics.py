import json
from typing import Optional, Union, Dict, Any

def _parse_numero(valor: Union[str, float, int, None]) -> Optional[float]:
    """
    Convierte un valor a float robustamente (bancario):
    - Quita separadores de miles y decimales, paréntesis, signos y moneda.
    - Maneja valores negativos por paréntesis o signo.
    - Retorna valor absoluto o None si es inválido.
    """
    if valor is None:
        return None
    if isinstance(valor, (int, float)):
        return abs(float(valor))
    if not isinstance(valor, str):
        return None

    s = valor.strip()
    if not s or s.lower() in ["na", "n/a", "sin dato"]:
        return None
    # Paréntesis = negativo
    negativo = False
    if s.startswith("(") and s.endswith(")"):
        s = s[1:-1]
        negativo = True
    # Quitar símbolos, moneda, espacios
    for simbolo in ["$", "USD", "MXN", "%", "+", "-"]:
        s = s.replace(simbolo, "")
    s = s.replace(",", "")  # Miles
    s = s.replace(".", "")  # Decimales (se espera solo enteros)
    try:
        val = float(s)
        return abs(val)
    except ValueError:
        return None

def safe_div(a: Optional[float], b: Optional[float]) -> Optional[float]:
    if a is None or b is None or b == 0:
        return None
    return round(a / b, 2)

def safe_sub(a: Optional[float], b: Optional[float]) -> Optional[float]:
    if a is None or b is None:
        return None
    return round(a - b, 2)

def safe_mul(a: Optional[float], b: Optional[float]) -> Optional[float]:
    if a is None or b is None:
        return None
    return round(a * b, 2)

def safe_add(a: Optional[float], b: Optional[float]) -> Optional[float]:
    if a is None and b is None:
        return None
    if a is None:
        return b
    if b is None:
        return a
    return round(a + b, 2)

def calcular_razones_financieras_bancario(
    datos_balance: Dict[str, Dict[str, Any]]
) -> Dict[str, Dict[str, Optional[float]]]:
    """
    Calcula razones financieras estándar bancarias para cada año.
    Maneja input inconsistente y nombres estándar del prompt.
    """
    salida: Dict[str, Dict[str, Optional[float]]] = {}
    ingresos_por_anio: Dict[str, Optional[float]] = {}
    utilidad_por_anio: Dict[str, Optional[float]] = {}
    activo_por_anio: Dict[str, Optional[float]] = {}
    dias = 365

    for anio in sorted(datos_balance.keys()):
        bal = {k.lower(): v for k, v in datos_balance.get(anio, {}).items()}

        # Activo Circulante
        bancos = _parse_numero(bal.get("bancos"))
        clientes = _parse_numero(bal.get("clientes"))
        inventarios = _parse_numero(bal.get("inventarios"))
        total_activo_circulante = _parse_numero(bal.get("total activo circulante"))

        # Pasivo y capital
        proveedores = _parse_numero(bal.get("proveedores"))
        total_pasivo_corto = _parse_numero(bal.get("total pasivo a corto plazo"))
        total_pasivo_largo = _parse_numero(bal.get("total pasivo a largo plazo"))
        total_pasivo = _parse_numero(bal.get("total pasivo"))
        capital_social = _parse_numero(bal.get("capital social"))
        utilidad_ejercicio = _parse_numero(bal.get("utilidad o pérdida del ejercicio"))
        total_capital_contable = _parse_numero(bal.get("total capital contable"))
        total_pasivo_y_capital = _parse_numero(bal.get("total pasivo y capital contable"))

        # Resultados
        ingresos = _parse_numero(bal.get("ingresos"))
        costos_venta = _parse_numero(bal.get("costos de venta y/o servicio"))

        total_activo = _parse_numero(bal.get("total activo"))

        # Para razones
        ingresos_por_anio[anio] = ingresos
        utilidad_por_anio[anio] = utilidad_ejercicio
        activo_por_anio[anio] = total_activo

        salida[anio] = {
            # Razones de liquidez
            "razon_corriente": safe_div(total_activo_circulante, total_pasivo_corto),  # (Activo Circulante / Pasivo CP)
            "prueba_acida": safe_div(safe_sub(safe_sub(total_activo_circulante, inventarios), bancos), total_pasivo_corto), # (Activo Circulante - Inventarios - Bancos) / Pasivo CP
            "capital_trabajo": safe_sub(total_activo_circulante, total_pasivo_corto),

            # Razones de endeudamiento
            "razon_endeudamiento": safe_div(total_pasivo, total_activo),  # Pasivo Total / Activo Total
            "razon_apalancamiento": safe_div(total_pasivo, total_capital_contable),  # Pasivo Total / Capital Contable
            "razon_endeudamiento_largo_plazo": safe_div(total_pasivo_largo, total_activo),  # Pasivo LP / Activo Total

            # Rentabilidad y márgenes
            "margen_utilidad": safe_div(utilidad_ejercicio, ingresos),  # Utilidad / Ventas
            "roa": safe_div(utilidad_ejercicio, total_activo),  # Utilidad / Activo Total
            "roe": safe_div(utilidad_ejercicio, total_capital_contable),  # Utilidad / Capital Contable

            # Eficiencia operativa (rotaciones)
            "rotacion_cartera": safe_div(ingresos, clientes),  # Ventas / Cuentas por cobrar
            "rotacion_inventario": safe_div(costos_venta, inventarios),  # Costos venta / Inventario
            "rotacion_proveedores": safe_div(costos_venta, proveedores),  # Costos venta / Proveedores

            # Cobertura y otros
            "cobertura_intereses": None,  # Solo si tienes gastos/intereses (agrega campo si está)
        }

    # Incrementos interanuales
    años = sorted(salida.keys())
    for i in range(1, len(años)):
        actual = años[i]
        anterior = años[i-1]
        vt, vt_prev = ingresos_por_anio.get(actual), ingresos_por_anio.get(anterior)
        ue, ue_prev = utilidad_por_anio.get(actual), utilidad_por_anio.get(anterior)
        at, at_prev = activo_por_anio.get(actual), activo_por_anio.get(anterior)

        delta_vt = safe_sub(vt, vt_prev)
        delta_ue = safe_sub(ue, ue_prev)
        delta_at = safe_sub(at, at_prev)

        salida[actual].update({
            "incremento_ventas_pct": safe_mul(safe_div(delta_vt, vt_prev), 100),
            "incremento_utilidad_pct": safe_mul(safe_div(delta_ue, ue_prev), 100),
            "incremento_activo_pct": safe_mul(safe_div(delta_at, at_prev), 100),
        })

    return salida

# Ejemplo de uso:
if __name__ == "__main__":
    datos1 = {
      "2019": {
        "Bancos": "10500",
        "Clientes": "2000",
        "Inventarios": "3500000",
        "Total Activo Circulante": "10500000",
        "Total Activo": "27869960",
        "Proveedores": "3000",
        "Total Pasivo a Corto Plazo": "6500",
        "Total Pasivo": "12721.65",
        "Capital Social": "5000",
        "Utilidad o pérdida del ejercicio": "456408",
        "Total Capital Contable": "15148.31",
        "Total Pasivo y Capital Contable": "26621.96",
        "Ingresos": "31084188",
        "Costos de venta y/o servicio": "24591962"
      },
      "2020": {
        "Bancos": "12000",
        "Clientes": "2500",
        "Inventarios": "4000000",
        "Total Activo Circulante": "12000000",
        "Total Activo": "34623840",
        "Proveedores": "3500",
        "Total Pasivo a Corto Plazo": "7000",
        "Total Pasivo": "16180.11",
        "Capital Social": "5000",
        "Utilidad o pérdida del ejercicio": "2020513",
        "Total Capital Contable": "18443.73",
        "Total Pasivo y Capital Contable": "34623.84",
        "Ingresos": "26507587",
        "Costos de venta y/o servicio": "18924541"
      }
    }
    razones = calcular_razones_financieras_bancario(datos1)
    print(json.dumps(razones, indent=2, ensure_ascii=False))
