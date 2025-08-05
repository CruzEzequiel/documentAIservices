import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

from controllers import info_controller, pdf_controller

# Cargar .env
load_dotenv()

app = FastAPI()

# Configuración de CORS desde variables de entorno
origins = os.getenv("CORS_ALLOW_ORIGINS", "").split(",")
credentials = os.getenv("CORS_ALLOW_CREDENTIALS", "false").lower() == "true"
methods = os.getenv("CORS_ALLOW_METHODS", "").split(",")
headers = os.getenv("CORS_ALLOW_HEADERS", "").split(",")

if origins != [""]:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=credentials,
        allow_methods=methods,
        allow_headers=headers,
    )
else:
    print("Advertencia: CORS no está configurado. Define CORS_ALLOW_ORIGINS en .env.")

# Registrar routers
app.include_router(info_controller.router)
app.include_router(pdf_controller.router)
