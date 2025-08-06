import os
import google.generativeai as genai
from fastapi import APIRouter, UploadFile, File, Body, Depends, HTTPException, status
from fastapi.responses import JSONResponse

from middlewares.auth_middleware import validate_access_token
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

MODEL_NAME = "gemini-2.5-flash-lite"

PROMPT_TEMPLATE = """
Dado el siguiente archivo PDF, determina si corresponde a un documento de tipo {tipo_doc}, considerando las posibles representaciones en México…
- Cedulario de identificación fiscal: RFC o cédula.
- Identificación del representante: INE o pasaporte.
- Poder notarial.
- Comprobante de domicilio fiscal.
- CURP.

Si es **{tipo_doc}**, responde 'True'. Si no, responde en español con el tipo detectado.
"""

@router.post("/analyze_pdf/{tipo_doc}")
async def analyze_pdf(
    tipo_doc: str,
    file: UploadFile = File(...),
    _: None = Depends(validate_access_token)
):
    local_path = None
    uploaded_file = None

    try:
        # 1) Guardar el UploadFile en disco
        local_path = await save_upload_file(file, UPLOAD_DIR)

        # 2) Subir el PDF a GeminiAI
        uploaded_file = genai.upload_file(local_path)

        # 3) Generar prompt y llamar al modelo
        prompt = PROMPT_TEMPLATE.format(tipo_doc=tipo_doc)
        model = genai.GenerativeModel(MODEL_NAME)
        resp = model.generate_content([prompt, uploaded_file])

        text = resp.text.strip()
        is_valid = "True" in text

        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={
                "tipo_doc": tipo_doc,
                "esDocumentoValido": is_valid,
                "documentoDetectado": text,
                "response": text
            }
        )
    except HTTPException:
        # Re-lanzar errores HTTP tal cual
        raise
    except Exception as e:
        print("Error al analizar PDF:", e)
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        # 4) Limpieza de recursos
        if uploaded_file:
            try:
                uploaded_file.delete()
            except Exception:
                pass
        if local_path:
            await delete_local_file(local_path)


@router.post("/analyze_url_pdf/{tipo_doc}")
async def analyze_url_pdf(
    tipo_doc: str,
    input: AnalyzeUrlPdfInput = Body(...),
    _: None = Depends(validate_access_token)
):
    temp_path = None
    uploaded_file = None

    try:
        # 1) Descargar el PDF desde la URL
        temp_path = download_pdf_from_url(input.downloadUrl)

        # 2) Subir el PDF a GeminiAI
        uploaded_file = genai.upload_file(temp_path)

        # 3) Generar prompt y llamar al modelo
        prompt = PROMPT_TEMPLATE.format(tipo_doc=tipo_doc)
        model = genai.GenerativeModel(MODEL_NAME)
        resp = model.generate_content([prompt, uploaded_file])

        text = resp.text.strip()
        is_valid = "True" in text

        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={
                "tipo_doc": tipo_doc,
                "esDocumentoValido": is_valid,
                "documentoDetectado": text,
                "response": text
            }
        )
    except HTTPException:
        raise
    except Exception as e:
        print("Error al analizar PDF desde URL:", e)
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        # 4) Limpieza de recursos
        if uploaded_file:
            try:
                uploaded_file.delete()
            except Exception:
                pass
        if temp_path:
            await delete_local_file(temp_path)
