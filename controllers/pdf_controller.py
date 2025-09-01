import os
import google.generativeai as genai
from fastapi import APIRouter, UploadFile, File, Body, Depends, HTTPException, status
from fastapi.responses import JSONResponse

from middlewares.auth_middleware_old import validate_access_static_token
from services.upload_file_service import save_upload_file, delete_local_file
from services.download_service import download_pdf_from_url
from schemas.analyze_schemas import AnalyzeUrlPdfInput

router = APIRouter()

# Directorio para almacenar archivos subidos
UPLOAD_DIR = "./uploaded_files"
os.makedirs(UPLOAD_DIR, exist_ok=True)

# Configuración de GeminiAI
API_KEY = os.getenv("GEMINI_API_KEY")
if not API_KEY:
    raise ValueError("Define 'GEMINI_API_KEY' en .env")
genai.configure(api_key=API_KEY)

GEMINI_MODELS = [
    "gemini-2.5-flash-lite",
    "gemini-2.5-flash",
    "gemini-2.5-pro",
]

# Prompt mejorado: instrucción clara, salida binaria, contexto mexicano y ejemplos de falsos positivos
PROMPT_TEMPLATE = """
Tu tarea es verificar si el archivo PDF corresponde a un documento de tipo **{tipo_doc}**, tal como se usa en México. 
Evalúa cuidadosamente, incluso si el formato varía, pero asegúrate de evitar confusiones con documentos parecidos.

**Instrucciones**:
- Si el PDF corresponde a un **{tipo_doc}**, responde exactamente: `True`
- Si no, responde SOLO con el tipo de documento detectado (ejemplo: "El documento corresponde a un INE", "El documento corresponde a una cédula fiscal", etc.)
- No agregues explicaciones ni comentarios adicionales.
- Si tienes dudas, responde con el tipo más probable.

**Ejemplo de respuesta válida**:
True
o
"El documento corresponde a un INE"
o
"El documento corresponde a una cédula fiscal"
"""

def log(msg: str):
    print(f"[ANALYZE_PDF] {msg}")

async def analyze_file(tipo_doc: str, local_path: str) -> dict:
    uploaded_file = None
    try:
        uploaded_file = genai.upload_file(local_path)
        prompt = PROMPT_TEMPLATE.format(tipo_doc=tipo_doc)
        last_error = None

        for model_name in GEMINI_MODELS:
            try:
                model = genai.GenerativeModel(model_name)
                log(f"Usando modelo {model_name} para '{tipo_doc}'...")
                response = model.generate_content([prompt, uploaded_file])
                text = response.text.strip()
                is_valid = text.strip() == "True"
                return {
                    "tipo_doc": tipo_doc,
                    "esDocumentoValido": is_valid,
                    "documentoDetectado": text,
                    "response": text,
                }
            except Exception as e:
                last_error = str(e)
                log(f"Error con modelo {model_name}: {e}")
                continue

        raise Exception(f"Todos los modelos fallaron. Último error: {last_error}")
    finally:
        if uploaded_file:
            try:
                uploaded_file.delete()
            except Exception as e:
                log(f"Error borrando archivo Gemini: {e}")

@router.post("/analyze_pdf/{tipo_doc}")
async def analyze_pdf(
    tipo_doc: str,
    file: UploadFile = File(...),
    _: None = Depends(validate_access_static_token),
):
    local_path = None
    try:
        local_path = await save_upload_file(file, UPLOAD_DIR)
        result = await analyze_file(tipo_doc, local_path)
        return JSONResponse(status_code=status.HTTP_200_OK, content=result)
    except HTTPException:
        raise
    except Exception as e:
        log(f"Error al analizar PDF: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if local_path:
            await delete_local_file(local_path)

@router.post("/analyze_url_pdf/{tipo_doc}")
async def analyze_url_pdf(
    tipo_doc: str,
    input: AnalyzeUrlPdfInput = Body(...),
    _: None = Depends(validate_access_static_token),
):
    temp_path = None
    try:
        temp_path = download_pdf_from_url(input.downloadUrl)
        result = await analyze_file(tipo_doc, temp_path)
        return JSONResponse(status_code=status.HTTP_200_OK, content=result)
    except HTTPException:
        raise
    except Exception as e:
        log(f"Error al analizar PDF desde URL: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if temp_path:
            await delete_local_file(temp_path)
