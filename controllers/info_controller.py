import os
import google.generativeai as genai
from fastapi import APIRouter, Body, HTTPException, Depends
from middlewares.auth_middleware import validate_access_token


router = APIRouter()

# Configurar Gemini
API_KEY = os.getenv("GEMINI_API_KEY")
if not API_KEY:
    raise ValueError("Define 'GEMINI_API_KEY' en .env")
genai.configure(api_key=API_KEY)

MODEL_NAME = "gemini-2.5-flash-lite"

ANALYZE_PROMPT = (
    "Usa únicamente la información proporcionada para responder.\n\n"
    "Contexto: {contexto}\nPregunta: {prompt}"
)

@router.post("/analyze_info")
async def analyze_info(
    data: dict = Body(...),
    _: None = Depends(validate_access_token)
):
    if not isinstance(data, dict):
        raise HTTPException(status_code=400, detail="Los datos deben ser un diccionario.")
    prompt = data.get("prompt")
    contexto = data.get("contexto")
    if not all(isinstance(x, str) for x in [prompt, contexto]):
        raise HTTPException(status_code=400, detail="Campos 'prompt' y 'contexto' deben ser texto.")

    try:
        full_prompt = ANALYZE_PROMPT.format(prompt=prompt, contexto=contexto)
        model = genai.GenerativeModel(MODEL_NAME)
        resp = model.generate_content([full_prompt])
        return {"summary": resp.text.strip()}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
