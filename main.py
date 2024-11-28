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

Si el archivo corresponde al tipo de documento **{tipo_doc}** o alguna de sus representaciones, responde con 'True'. Si no, responde con el tipo de documento que crees que es, basándote en las representaciones proporcionadas.
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
