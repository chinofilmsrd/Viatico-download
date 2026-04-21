# Etapa 1: Backend (Python/Flask)
FROM python:3.11-slim as backend
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt gunicorn
COPY backend.py .

# Etapa 2: Servidor Web (NGINX) para el Frontend
FROM nginx:alpine
# Copia el frontend a la carpeta que NGINX servirá
COPY frontend /usr/share/nginx/html
# Copia el backend y su entorno desde la etapa anterior
COPY --from=backend /app /app
COPY --from=backend /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=backend /usr/local/bin /usr/local/bin
# Instala Python en la imagen final de NGINX (necesario para ejecutar el backend)
RUN apk add --no-cache python3
# Copia un script de inicio
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh
COPY nginx.conf /etc/nginx/nginx.conf
EXPOSE 80
ENTRYPOINT ["/entrypoint.sh"]