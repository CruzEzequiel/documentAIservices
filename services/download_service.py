import tempfile
import httpx
from fastapi import HTTPException

def download_pdf_from_url(source_url: str) -> str:
    """
    Descarga el contenido de source_url y lo guarda en un archivo .pdf temporal.
    Devuelve la ruta al archivo.
    """
    # Asegurarse de trabajar con str
    url_str = str(source_url)

    http_response = httpx.get(url_str, timeout=30)
    if http_response.status_code != 200:
        raise HTTPException(
            status_code=400,
            detail=f"No se pudo descargar el PDF (status {http_response.status_code})."
        )

    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
        tmp.write(http_response.content)
        return tmp.name
