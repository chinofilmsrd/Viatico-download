FROM python:3.11-slim

WORKDIR /app

# Instalar FFmpeg y limpiar caché para reducir tamaño
RUN apt-get update && \
    apt-get install -y ffmpeg && \
    rm -rf /var/lib/apt/lists/*

# Copiar archivo de dependencias
COPY requirements.txt .

# Instalar dependencias de Python
RUN pip install --no-cache-dir -r requirements.txt

# Copiar el código del backend
COPY backend.py .

# Copiar el frontend (carpeta completa)
COPY frontend ./frontend

# Exponer el puerto 80 (Back4app espera este puerto por defecto)
EXPOSE 80

# Comando de inicio
CMD ["python", "backend.py"]
