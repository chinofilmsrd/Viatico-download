FROM python:3.11-slim

WORKDIR /app

# --- Diagnóstico inicial ---
RUN echo "=== 1. Sistema operativo ===" && cat /etc/os-release
RUN echo "=== 2. Versión de Python ===" && python --version
RUN echo "=== 3. Instalando FFmpeg ==="

# Instalar FFmpeg (con salida detallada)
RUN apt-get update && \
    apt-get install -y ffmpeg && \
    rm -rf /var/lib/apt/lists/*

RUN echo "=== 4. FFmpeg instalado. Versión: ===" && ffmpeg -version | head -n 1

# Copiar requirements.txt y mostrar su contenido
COPY requirements.txt .
RUN echo "=== 5. Contenido de requirements.txt ===" && cat requirements.txt

# Instalar dependencias Python con salida verbosa
RUN pip install --no-cache-dir --verbose -r requirements.txt

RUN echo "=== 6. Dependencias instaladas. Listado: ===" && pip list

# Copiar el código del backend
COPY backend.py .
RUN echo "=== 7. backend.py copiado. Primeras 5 líneas: ===" && head -n 5 backend.py

# Copiar el frontend
COPY frontend ./frontend
RUN echo "=== 8. Frontend copiado. Contenido de frontend: ===" && ls -la frontend/

EXPOSE 80

CMD ["python", "backend.py"]
