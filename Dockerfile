FROM node:18-bookworm

# Instalar ffmpeg y wget para descargar la última versión de yt-dlp
RUN apt-get update && \
    apt-get install -y ffmpeg python3 wget && \
    rm -rf /var/lib/apt/lists/*

# Descargar el binario oficial de Linux de yt-dlp
RUN wget -O /usr/local/bin/yt-dlp https://github.com/yt-dlp/yt-dlp/releases/latest/download/yt-dlp && \
    chmod a+rx /usr/local/bin/yt-dlp

# Crear y usar la carpeta de la app
WORKDIR /app

# Instalar dependencias de Node
COPY package*.json ./
RUN npm install

# Copiar el resto del código
COPY . .

# Exponer el puerto
EXPOSE 5001

# Iniciar la app
CMD ["node", "server.js"]
