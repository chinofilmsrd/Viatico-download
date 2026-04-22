FROM python:3.11-slim

WORKDIR /app

# Instalar FFmpeg (necesario para yt-dlp en conversiones)
RUN apt-get update && apt-get install -y ffmpeg && rm -rf /var/lib/apt/lists/*

# Copiar e instalar dependencias Python
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copiar el backend
COPY backend.py .

# Copiar el frontend (carpeta completa)
COPY frontend ./frontend

# Exponer puerto 80
EXPOSE 80

# Comando de inicio
CMD ["python", "backend.py"]