from fastapi import FastAPI, File, UploadFile, HTTPException, Depends, Header, status
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import os
import google.generativeai as genai
from dotenv import load_dotenv

load_dotenv()

app = FastAPI()

# Leer configuraciones de CORS desde las variables de entorno
CORS_ALLOW_ORIGINS = os.getenv("CORS_ALLOW_ORIGINS", "").split(",")  # Lista de dominios permitidos (vacío por defecto)
CORS_ALLOW_CREDENTIALS = os.getenv("CORS_ALLOW_CREDENTIALS", "false").lower() == "true"
CORS_ALLOW_METHODS = os.getenv("CORS_ALLOW_METHODS", "").split(",")  # Métodos permitidos (vacío por defecto)
CORS_ALLOW_HEADERS = os.getenv("CORS_ALLOW_HEADERS", "").split(",")  # Encabezados permitidos (vacío por defecto)

# Habilitar CORS solo si se configuran valores válidos en el .env
if CORS_ALLOW_ORIGINS != [""]:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=CORS_ALLOW_ORIGINS,
        allow_credentials=CORS_ALLOW_CREDENTIALS,
        allow_methods=CORS_ALLOW_METHODS,
        allow_headers=CORS_ALLOW_HEADERS,
    )
else:
    print("Advertencia: CORS no está configurado. Asegúrate de configurarlo en el archivo .env.")

# Carpeta donde se guardarán los PDFs
UPLOAD_DIR = "./uploaded_files"
os.makedirs(UPLOAD_DIR, exist_ok=True)

# Configurar la API Key de GeminiAI
API_KEY = os.getenv("GEMINI_API_KEY")  # Asegúrate de definir esta variable de entorno
if not API_KEY:
    raise ValueError("La API Key de GeminiAI no está configurada. Define la variable 'GEMINI_API_KEY'.")

# Configuración del modelo y prompt
MODEL = 'gemini-1.5-flash'

PROMPT_TEMPLATE = """
Dado el siguiente archivo PDF, determina si corresponde a un documento de tipo {tipo_doc}, considerando las posibles representaciones de este tipo de documento en México. A continuación se proporciona una lista de documentos y sus posibles representaciones:

- **Cedulario de identificación fiscal**: puede ser el Registro Federal de Contribuyentes (RFC) o la cédula fiscal.
- **Identificación del representante**: puede ser la credencial para votar (INE) o el pasaporte.
- **Poder notarial**: documento legal que otorga poderes a un representante.
- **Comprobante de domicilio fiscal**: puede ser un recibo bancario, de teléfono, luz, agua u otro servicio, siempre que contenga la dirección del cliente.
- **CURP**: Clave Única de Registro de Población.

Si el archivo corresponde al tipo de documento **{tipo_doc}** o alguna de sus representaciones, responde con 'True'. Si no corresponde, responde en español con el tipo de documento que crees que es, basándote en las representaciones proporcionadas.
"""

# Configurar GeminiAI
genai.configure(api_key=API_KEY)

# Leer el token de acceso desde las variables de entorno
ACCESS_TOKEN = os.getenv("ACCESS_TOKEN")

if not ACCESS_TOKEN:
    raise ValueError("El token de acceso no está configurado. Define 'ACCESS_TOKEN' en el archivo .env.")

# Dependencia para validar el token
def validate_access_token(authorization: str = Header(None)):
    if not authorization:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token de acceso requerido.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if authorization != f"Bearer {ACCESS_TOKEN}":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Token de acceso inválido.",
        )

# Endpoint protegido
@app.post("/analyze_pdf/{tipo_doc}")
async def analyze_pdf(tipo_doc: str, file: UploadFile = File(...), _: None = Depends(validate_access_token)):
    try:
        # Guardar el archivo PDF subido temporalmente
        pdf_path = os.path.join(UPLOAD_DIR, file.filename)
        with open(pdf_path, "wb") as buffer:
            buffer.write(await file.read())
        
        # Subir el archivo PDF a Gemini
        uploaded_file = genai.upload_file(pdf_path)
        
        # Crear el prompt para la API de Gemini
        prompt = PROMPT_TEMPLATE.format(tipo_doc=tipo_doc)
        
        # Consultar la API de Gemini para analizar el archivo
        model = genai.GenerativeModel(MODEL)
        response = model.generate_content([prompt, uploaded_file])
        
        # Determinar si la clasificación es "True" o "False"
        is_valid_document = "True" in response.text
        
        # Si no es del tipo solicitado, extraer el tipo de documento detectado
        detected_document_type = response.text.strip()
        
        return JSONResponse(content={
            "tipo_doc": tipo_doc,
            "esDocumentoValido": is_valid_document,
            "documentoDetectado": detected_document_type,
            "response": response.text
        })
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al procesar el archivo: {str(e)}")
    finally:
        # Eliminar archivo en Gemini
        try:
            if 'uploaded_file' in locals():
                uploaded_file.delete()
        except Exception as gemini_error:
            print(f"Error al eliminar archivo en Gemini: {gemini_error}")
        
        # Eliminar archivo local
        try:
            if os.path.exists(pdf_path):
                os.remove(pdf_path)
        except Exception as local_error:
            print(f"Error al eliminar archivo local: {local_error}")


EXTRACT_INFO_TEMPLATE = """ Extrae toda la información estructurada posible de este documento {tipo_doc} y conviértela en un array de objetos con el siguiente formato:

[
    {{ "name": "Nombre del Campo", "value": "valor extraído" }},
    {{ "name": "Otro Campo", "value": "otro valor extraído" }}
];

si encuentras estos datos devuélvelos con el nombre indicado en esta sección. **

    solicitante: Nombre de la empresa o persona que solicita el crédito.

    rfc: Registro Federal de Contribuyentes del solicitante.

    pais_registro: País donde está registrada la empresa.

    filtro_pais: Restricción sobre el país de constitución de la empresa.

    fecha_constitucion: Fecha en que se constituyó la empresa.

    tipo_producto: Tipo de producto financiero solicitado.

    tipo_credito: Tipo de crédito solicitado (ejemplo: Revolvente, Simple, etc.).

    destino: Uso que se dará al crédito.

    monto_moneda: Monto solicitado y la moneda en la que se expresa.

    fuente_pago: Origen de los fondos con los que se pagará el crédito.

    plazo_credito: Duración del crédito en años o meses.

    periodo_gracia: Tiempo en el que no se requerirá pago del crédito.

    periodicidad_pagos: Frecuencia con la que se realizarán los pagos (mensual, trimestral, etc.).

    garantias: Tipo de garantía ofrecida para respaldar el crédito.

    obligado_solidario: Persona o entidad que garantiza el crédito junto con el solicitante.

    credito_sindicado: Indica si el crédito es compartido entre varias instituciones financieras.

    fecha_consulta: Fecha en que se realizó la consulta al buró de crédito.

    mop: Nivel de cumplimiento de pagos en buró de crédito.

    calificacion_cartera: Clasificación del crédito en términos de riesgo.

    tiene_claves_prevencion: Indica si el buró reporta claves de prevención.

    atrasos_credito: Indica si el solicitante ha tenido retrasos en pagos.

    evidencia_incumplimiento: Indica si hay evidencia de incumplimiento de pagos.

    incidencia_legal: Indica si hay registros legales en buró de crédito.

    descripcion_incidencia: Descripción de cualquier incidencia legal.

    tiene_credito_nafin: Indica si el solicitante ya tiene un crédito con Nafin.

    detalle_empresas: Información sobre empresas relacionadas con el solicitante.

    investigacion_previa: Resultado de investigaciones previas sobre el solicitante.

    pep_involucrado: Indica si hay Personas Políticamente Expuestas involucradas.

    detalles_cargos: Detalles sobre cargos políticos o legales del solicitante.

    actividades_riesgo: Indica si el solicitante participa en actividades de alto riesgo.

    calificacion_experta: Evaluación del crédito según expertos.

    categorizacion_saras: Clasificación del crédito en el sistema SARAS.

    anexo1: Información complementaria relevante.

    anexo2: Información adicional aplicable. **

La extracción debe ser precisa y mantener el contexto de cada entidad dentro del documento. La respuesta debe ser exclusivamente el JSON, sin explicaciones, comentarios ni texto adicional."""


# Endpoint protegido
@app.post("/extract_pdf/{tipo_doc}")
async def extract_pdf(tipo_doc: str, file: UploadFile = File(...), _: None = Depends(validate_access_token)):
    try:
        # Guardar el archivo PDF subido temporalmente
        pdf_path = os.path.join(UPLOAD_DIR, file.filename)
        with open(pdf_path, "wb") as buffer:
            buffer.write(await file.read())
        
        # Subir el archivo PDF a Gemini
        uploaded_file = genai.upload_file(pdf_path)
        
        # Crear el prompt para la API de Gemini
        prompt = EXTRACT_INFO_TEMPLATE.format(tipo_doc=tipo_doc)
        
        # Consultar la API de Gemini para analizar el archivo
        model = genai.GenerativeModel(MODEL)
        response = model.generate_content([prompt, uploaded_file])
        
        # Determinar si la clasificación es "True" o "False"
        
        return JSONResponse(content={
            "tipo_doc": tipo_doc,
            "extracted": response.text
        })
    except Exception as e:
        print(e)
        raise HTTPException(status_code=500, detail=f"Error al procesar el archivo: {str(e)}")
    finally:
        # Eliminar archivo en Gemini
        try:
            if 'uploaded_file' in locals():
                uploaded_file.delete()
        except Exception as gemini_error:
            print(f"Error al eliminar archivo en Gemini: {gemini_error}")
        
        # Eliminar archivo local
        try:
            if os.path.exists(pdf_path):
                os.remove(pdf_path)
        except Exception as local_error:
            print(f"Error al eliminar archivo local: {local_error}")


@app.post("/analyze_info")
async def analyze_info(data: dict, _: None = Depends(validate_access_token)):
    # Validación manual de datos
    if not isinstance(data, dict):
        raise HTTPException(status_code=400, detail="Los datos deben ser un diccionario.")
    
    prompt = data.get("prompt")
    contexto = data.get("contexto")

    if not isinstance(prompt, str) or not isinstance(contexto, str):
        raise HTTPException(status_code=400, detail="Los campos 'prompt' y 'contexto' deben ser cadenas de texto.")

    try:
        # Crear el prompt para la API de Gemini
        full_prompt = ANALYZE_PROMPT.format(prompt=prompt, contexto=contexto)
        
        # Consultar la API de Gemini para analizar la información
        model = genai.GenerativeModel(MODEL)
        response = model.generate_content([full_prompt])
        
        return {"summary": response.text}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al procesar la solicitud: {str(e)}")
    
ANALYZE_PROMPT = "Contexto: {contexto}\nPregunta: {prompt}"