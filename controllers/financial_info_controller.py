import os
import json
import re
import google.generativeai as genai
from fastapi import APIRouter, Body, Depends, HTTPException, status
from fastapi.responses import JSONResponse

from middlewares.auth_middleware import validate_access_token
from services.download_service import download_pdf_from_url
from schemas.analyze_schemas import AnalyzeUrlPdfInput
from utils.financialAnalitics import calcular_razones_financieras_bancario
from utils.templates import PROMPT_ESTADO_SITUACION_FINANCIERA

router = APIRouter()

# Configuración Gemini
API_KEY = os.getenv("GEMINI_API_KEY")
if not API_KEY:
    raise ValueError("Define 'GEMINI_API_KEY' en .env")
genai.configure(api_key=API_KEY)
MODEL_NAME = "gemini-2.5-flash-lite"

def extract_json(text):
    """
    Extrae el primer bloque JSON de una respuesta de LLM, eliminando encabezados tipo markdown.
    """
    md_json = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if md_json:
        text = md_json.group(1)
    text = text.strip()
    try:
        return json.loads(text)
    except Exception:
        matches = re.findall(r'(\{.*\})', text, re.DOTALL)
        for m in matches:
            try:
                return json.loads(m)
            except Exception:
                continue
    raise ValueError("No se encontró un JSON válido en la respuesta.")
    """
    Recibe una lista de archivos (uno por año), extrae los datos de cada uno usando Gemini,
    arma el dict {año: datos} y calcula razones financieras multi-anuales.
    """
    datos_por_anio = {}
    archivos_tmp = []
    archivos_subidos = []

    model = genai.GenerativeModel(MODEL_NAME)

    try:
        # Procesa cada archivo recibido
        for input in inputs:
            temp_path = download_pdf_from_url(input.downloadUrl)
            archivos_tmp.append(temp_path)
            uploaded_file = genai.upload_file(temp_path)
            archivos_subidos.append(uploaded_file)

            prompt1 = PROMPT_ESTADO_SITUACION_FINANCIERA.substitute(context="(El PDF irá adjunto, NO EN TEXTO)")
            resp1 = model.generate_content([prompt1, uploaded_file])
            text1 = resp1.text.strip()

            try:
                datos1 = extract_json(text1)
            except Exception as e:
                print("Error al parsear estado de situación financiera:", text1, e)
                raise HTTPException(status_code=500, detail="Error al parsear JSON de situación financiera.")

            # Esperamos que datos1 tenga la forma {'2022': {...campos...}}
            for anio, datos in datos1.items():
                datos_por_anio[anio] = datos

        # Una vez extraída la info de todos los años, calcular razones financieras
        razones = calcular_razones_financieras_bancario(datos_por_anio)
        print("Datos de situación financiera por año:", datos_por_anio)
        print("Razones financieras calculadas:", razones)

        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content=razones
        )

    except HTTPException:
        raise
    except Exception as e:
        print("Error general:", e)
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        # Limpieza de archivos temporales/subidos
        for uploaded_file in archivos_subidos:
            try:
                uploaded_file.delete()
            except Exception:
                pass
        for temp_path in archivos_tmp:
            if temp_path and os.path.exists(temp_path):
                os.remove(temp_path)

@router.post("/financial/analytics", dependencies=[Depends(validate_access_token)])
async def analisis_financiero_batch(inputs: list[AnalyzeUrlPdfInput] = Body(...)):
    """
    Recibe una lista de archivos (uno por año), extrae los datos de cada uno usando Gemini,
    arma el dict {año: datos} y calcula razones financieras multi-anuales.
    """
    datos_por_anio = {}
    archivos_tmp = []
    archivos_subidos = []

    model = genai.GenerativeModel(MODEL_NAME)

    try:
        # Procesa cada archivo recibido
        for input in inputs:
            temp_path = download_pdf_from_url(input.downloadUrl)
            archivos_tmp.append(temp_path)
            uploaded_file = genai.upload_file(temp_path)
            archivos_subidos.append(uploaded_file)

            prompt1 = PROMPT_ESTADO_SITUACION_FINANCIERA.substitute(context="(El PDF irá adjunto, NO EN TEXTO)")
            resp1 = model.generate_content([prompt1, uploaded_file])
            text1 = resp1.text.strip()

            try:
                datos1 = extract_json(text1)
            except Exception as e:
                print("Error al parsear estado de situación financiera:", text1, e)
                raise HTTPException(status_code=500, detail="Error al parsear JSON de situación financiera.")

            # Esperamos que datos1 tenga la forma {'2022': {...campos...}}
            for anio, datos in datos1.items():
                datos_por_anio[anio] = datos

        # Una vez extraída la info de todos los años, calcular razones financieras
        razones = calcular_razones_financieras_bancario(datos_por_anio)
        print("Datos de situación financiera por año:", datos_por_anio)
        print("Razones financieras calculadas:", razones)

        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={
                "datos_por_anio": datos_por_anio,
                "razones": razones
            }
        )

    except HTTPException:
        raise
    except Exception as e:
        print("Error general:", e)
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        # Limpieza de archivos temporales/subidos
        for uploaded_file in archivos_subidos:
            try:
                uploaded_file.delete()
            except Exception:
                pass
        for temp_path in archivos_tmp:
            if temp_path and os.path.exists(temp_path):
                os.remove(temp_path)


@router.post("/financial/analytics/external", summary="Recalcula razones a partir de datos completados")
async def recalcula_razones(datos_por_anio: dict = Body(...)):
    """
    Recibe un dict {año: datos} directamente (completado/corregido por el usuario)
    y devuelve las razones financieras calculadas.
    """
    try:
        # Validar que el dict tenga al menos un año y campos esperados
        if not datos_por_anio or not isinstance(datos_por_anio, dict):
            raise HTTPException(status_code=400, detail="Formato inválido de datos_por_anio")
        # (Opcional: Validar estructura por año y campos clave)

        razones = calcular_razones_financieras_bancario(datos_por_anio)
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={"razones": razones}
        )
    except HTTPException:
        raise
    except Exception as e:
        print("Error en recalculo de razones:", e)
        raise HTTPException(status_code=500, detail=str(e))
