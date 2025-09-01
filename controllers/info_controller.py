import os
import google.generativeai as genai
from fastapi import APIRouter, Body, HTTPException, Depends
from middlewares.auth_middleware import validate_access_token

router = APIRouter()

API_KEY = os.getenv("GEMINI_API_KEY")
if not API_KEY:
    raise ValueError("Define 'GEMINI_API_KEY' en .env")
genai.configure(api_key=API_KEY)

GEMINI_MODELS = [
    "gemini-2.5-flash-lite",
    "gemini-2.5-flash",
    "gemini-2.5-pro",
]

ANALYZE_PROMPT = (
    "Usa únicamente la información proporcionada para responder.\n\n"
    "Contexto: {contexto}\nPregunta: {prompt}"
)

def get_model_response(full_prompt: str, model_name: str):
    model = genai.GenerativeModel(model_name)
    resp = model.generate_content([full_prompt])
    return resp.text.strip()

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

    full_prompt = ANALYZE_PROMPT.format(prompt=prompt, contexto=contexto)
    last_error = None

    for model_name in GEMINI_MODELS:
        try:
            summary = get_model_response(full_prompt, model_name)
            return {"summary": summary}
        except Exception as e:
            last_error = str(e)
            continue

    raise HTTPException(status_code=500, detail=str(last_error))
