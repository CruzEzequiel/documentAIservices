# Usa una imagen base de Python
FROM python:3.11-slim

# Establece el directorio de trabajo
WORKDIR /app

# Copia los archivos del proyecto al contenedor
COPY . /app

# Instala las dependencias desde el archivo requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Expone el puerto 8080, que es el que utilizará FastAPI
EXPOSE 8000

# Comando para ejecutar la aplicación FastAPI usando Uvicorn
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
