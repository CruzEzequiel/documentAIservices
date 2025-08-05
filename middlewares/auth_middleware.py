import os
from fastapi import Header, HTTPException, status
from dotenv import load_dotenv

load_dotenv()

ACCESS_TOKEN = os.getenv("ACCESS_TOKEN")
if not ACCESS_TOKEN:
    raise ValueError("Define 'ACCESS_TOKEN' en .env")

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
