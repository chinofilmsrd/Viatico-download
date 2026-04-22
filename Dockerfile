FROM python:3.11-slim

WORKDIR /app

# Instalar FFmpeg
RUN apt-get update && apt-get install -y ffmpeg && rm -rf /var/lib/apt/lists/*

# Copiar dependencias
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copiar backend
COPY backend.py .

# Copiar frontend
COPY frontend ./frontend

EXPOSE 80

CMD ["python", "backend.py"]

FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y ffmpeg && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# ---- Depuración ----
RUN python --version
RUN pip list
# -------------------

COPY backend.py .
COPY frontend ./frontend

EXPOSE 80
CMD ["python", "backend.py"]
