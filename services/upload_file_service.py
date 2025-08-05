import os
from fastapi import UploadFile

async def save_upload_file(
    upload: UploadFile,
    destination_dir: str
) -> str:
    """
    Guarda un UploadFile en destination_dir y devuelve la ruta al archivo.
    """
    if not destination_dir:
        raise ValueError("destination_dir no puede ser None al guardar un UploadFile")

    file_path = os.path.join(destination_dir, upload.filename)
    # Escritura síncrona, idéntica al monolito
    with open(file_path, "wb") as out_buffer:
        out_buffer.write(await upload.read())
    return file_path

async def delete_local_file(path: str) -> None:
    """
    Elimina un archivo local si existe.
    """
    try:
        if os.path.exists(path):
            os.remove(path)
    except Exception:
        pass
