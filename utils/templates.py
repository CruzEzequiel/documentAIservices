from string import Template

PROMPT_ESTADO_SITUACION_FINANCIERA = Template("""
Eres un analista financiero senior, experto en normatividad bancaria y en interpretación de estados financieros mexicanos, con experiencia en procesos de análisis crediticio para instituciones financieras.

## TU OBJETIVO:
Extrae y normaliza los **valores numéricos exactos** de los siguientes conceptos, **por año**, usando un objeto JSON con claves estandarizadas.

**MUY IMPORTANTE:**
- Identifica **todas las formas, sinónimos, abreviaturas, y variantes** en que cada concepto podría aparecer (ejemplo: "Clientes", "Cuentas por cobrar", "CXC", "Deudores", etc.).
- Normaliza diferencias por mayúsculas/minúsculas, acentos, uso de guiones, signos o paréntesis, errores ortográficos comunes, y expresiones propias de la contabilidad mexicana.
- Si el valor aparece entre paréntesis (ejemplo: (12,300)), es negativo, pero **extrae solo el valor absoluto** y sin paréntesis.
- Elimina **todos los símbolos, puntos decimales, comas, espacios, signos, letras, ni símbolos de moneda**. **Solo extrae números enteros**.
- Si un concepto no existe, es cero, o está vacío, **registra su clave con una cadena vacía ""**.
- No infieras, calcules ni completes ningún dato que no esté de forma explícita.
- Incluye un campo si y solo si su nombre o sinónimo aparece explícitamente en el contexto proporcionado.

**LISTA DE CONCEPTOS ESTÁNDAR (usa estas claves exactas en el JSON):**
- Bancos (Disponibilidades, Efectivo, Cuentas bancarias)
- Clientes (Cuentas por cobrar, CXC, Deudores)
- Inventarios (Existencias, Stock, Mercancía)
- Total Activo Circulante (Activo corriente, Suma activo circulante)
- Total Activo No Circulante (Activo no corriente)
- Total Activo
- Proveedores (Cuentas por pagar, Acreedores, CXP)
- Total Pasivo a Corto Plazo (Pasivo circulante)
- Total Pasivo a Largo Plazo (Pasivo no circulante)
- Total Pasivo
- Capital Social (Capital pagado, Capital suscrito)
- Utilidad o pérdida del ejercicio (Resultado neto, Utilidad neta)
- Total Capital Contable (Patrimonio, Capital contable)
- Total Pasivo y Capital Contable (Suma pasivo y capital)
- Ingresos (Ventas, Ingresos operativos)
- Costos de venta y/o servicio (Costos ventas, Costos servicios)

**Estructura tu respuesta JSON así:**
{
  "2023": {
    "Bancos": "valor",
    "Clientes": "valor",
    "Inventarios": "valor",
    ... // todos los campos, con "" si no están
  },
  "2022": {
    ...
  }
}

### CONTEXTO PROPORCIONADO:
$context

### RESPUESTA:
""".strip())





PROMPT_RESULTADO_INTEGRAL = Template("""
Eres un experto en análisis financiero especializado en estados de resultado integral auditados.  
Tu tarea es identificar y extraer desde el contexto proporcionado los valores numéricos explícitos para estos tres conceptos, organizados por año:

**IMPORTANTE:**  
- Si un valor aparece entre paréntesis (ejemplo: (1000)), esto representa una cantidad negativa o pérdida, pero **solo extrae el valor absoluto** (ejemplo: "1000").
- No incluyas signos de más (+), menos (-), símbolos de moneda, letras, comas, puntos decimales ni ningún tipo de notación, solo el número entero correspondiente.
- Si el valor está vacío, es cero o no está presente, omítelo en el JSON.
- El resultado debe ser un único objeto JSON, donde cada clave es el nombre del campo y su valor es un string que representa la cantidad extraída (sin ningún símbolo ni signo).

- Ingresos  
- Costos de venta y/o servicio  
- Utilidad o pérdida del ejercicio  

Construye la respuesta en formato JSON, respetando la siguiente estructura (con uno o más años):

{
  "AÑO": {
    "Ingresos": "…",
    "Costos de venta y/o servicio": "…",
    "Utilidad o pérdida del ejercicio": "…"
  },
  "...otros años encontrados...": {
    ...
  }
}

Instrucciones:
1. Extrae únicamente valores explícitos y claramente identificables en el contexto.
2. Para cada año que aparezca en el contexto, crea una entrada con ese año como clave.
3. Si algún campo no aparece en el texto, déjalo como cadena vacía "".
4. No realices cálculos, inferencias ni incluyas conceptos adicionales.
5. Respeta exactamente la sintaxis de la variable datos2 mostrada arriba.

### CONTEXTO PROPORCIONADO:
$context

### RESPUESTA:
""".strip())
