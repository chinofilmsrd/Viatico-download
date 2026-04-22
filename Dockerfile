FROM python:3.11-slim

WORKDIR /app

# Instalar FFmpeg (necesario para yt-dlp en conversiones)
RUN apt-get update && apt-get install -y ffmpeg && rm -rf /var/lib/apt/lists/*

# Copiar e instalar dependencias Python
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copiar el backend
COPY backend.py .

# Copiar cookies.txt para autenticación con YouTube
COPY cookies.txt .

# Copiar el frontend (carpeta completa)
COPY frontend ./frontend

# Exponer el puerto 80 (Back4app espera este puerto por defecto para Containers)
EXPOSE 80

# Comando de inicio
CMD ["python", "backend.py"]