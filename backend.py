"""
Backend para VoidDown - YouTube Downloader
Requisitos: Python 3.8+, yt-dlp, Flask, flask-cors
Ejecutar: python backend.py
"""

import os
import re
import tempfile
import logging
from pathlib import Path

from flask import Flask, request, send_file, jsonify, send_from_directory
from flask_cors import CORS
import yt_dlp

# Configuración de logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app)  # Permite peticiones desde el frontend (origen cruzado)

# Servir el frontend estático desde la carpeta 'frontend'
@app.route('/')
def serve_frontend():
    return send_from_directory('frontend', 'index.html')

@app.route('/<path:path>')
def serve_static(path):
    return send_from_directory('frontend', path)

# Carpeta temporal para descargas (se limpia automáticamente al cerrar)
DOWNLOAD_DIR = Path(tempfile.gettempdir()) / "voiddown_downloads"
DOWNLOAD_DIR.mkdir(exist_ok=True)

# Opciones base para yt-dlp
BASE_OPTS = {
    'quiet': True,
    'no_warnings': True,
    'extract_flat': False,
    'noplaylist': True,
    'socket_timeout': 30,
    'retries': 3,
    'fragment_retries': 3,
    'geo_bypass': True,
    'geo_bypass_country': 'US',
}

def sanitize_filename(name: str) -> str:
    """Elimina caracteres no válidos para nombres de archivo en Windows."""
    return re.sub(r'[<>:"/\\|?*]', '_', name)

def get_video_info(url: str) -> dict:
    """Extrae metadatos del video (título, miniatura, duración, etc.)"""
    ydl_opts = {
        **BASE_OPTS,
        'skip_download': True,
        'quiet': True,
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        try:
            info = ydl.extract_info(url, download=False)
        except Exception as e:
            logger.error(f"Error extrayendo info: {e}")
            raise ValueError(f"No se pudo obtener información del video: {e}")
        
        # Filtrar solo lo necesario
        return {
            'id': info.get('id'),
            'title': info.get('title', 'Sin título'),
            'thumbnail': info.get('thumbnail', ''),
            'duration': info.get('duration', 0),
            'uploader': info.get('uploader', 'Desconocido'),
            'formats': [
                {
                    'format_id': f['format_id'],
                    'ext': f['ext'],
                    'resolution': f.get('resolution'),
                    'filesize': f.get('filesize'),
                    'vcodec': f.get('vcodec'),
                    'acodec': f.get('acodec'),
                    'format_note': f.get('format_note'),
                }
                for f in info.get('formats', [])
                if f.get('vcodec') != 'none' or f.get('acodec') != 'none'
            ]
        }

def download_video(url: str, format_id: str = None, quality: str = '720p') -> Path:
    """
    Descarga el video con el formato especificado.
    Si format_id es None, selecciona automáticamente el mejor ≤ quality.
    """
    output_template = str(DOWNLOAD_DIR / '%(title)s.%(ext)s')
    
    ydl_opts = {
        **BASE_OPTS,
        'outtmpl': output_template,
        'restrictfilenames': True,
    }
    
    if format_id:
        ydl_opts['format'] = format_id
    else:
        # Construir selector de formato: mejor video ≤ altura + mejor audio
        height = quality.replace('p', '') if quality != 'original' else ''
        if height:
            ydl_opts['format'] = f'bestvideo[height<={height}]+bestaudio/best[height<={height}]/best'
        else:
            ydl_opts['format'] = 'bestvideo+bestaudio/best'
    
    # Añadir postprocesador para mp3 si se solicita
    if format_id == 'mp3':
        ydl_opts['format'] = 'bestaudio/best'
        ydl_opts['postprocessors'] = [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '192',
        }]
        ydl_opts['outtmpl'] = str(DOWNLOAD_DIR / '%(title)s.%(ext)s')
    
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        try:
            info = ydl.extract_info(url, download=True)
            filename = ydl.prepare_filename(info)
            
            # Si se procesó a mp3, la extensión cambia
            if format_id == 'mp3':
                filename = str(Path(filename).with_suffix('.mp3'))
            
            filepath = Path(filename)
            if not filepath.exists():
                # Buscar archivo con extensión mp3 por si cambió nombre
                possible = list(DOWNLOAD_DIR.glob(f"{info.get('title')}*.mp3"))
                if possible:
                    filepath = possible[0]
                else:
                    raise FileNotFoundError("Archivo no encontrado después de descarga")
            
            return filepath
        except Exception as e:
            logger.error(f"Error en descarga: {e}")
            raise RuntimeError(f"Fallo en la descarga: {e}")

def cleanup_old_files(max_age_minutes: int = 60):
    """Elimina archivos temporales antiguos."""
    import time
    now = time.time()
    for f in DOWNLOAD_DIR.glob('*'):
        if f.is_file() and (now - f.stat().st_mtime) > (max_age_minutes * 60):
            try:
                f.unlink()
                logger.info(f"Limpieza: {f.name} eliminado")
            except Exception as e:
                logger.warning(f"No se pudo eliminar {f}: {e}")

# ------------------- ENDPOINTS -------------------

@app.route('/info', methods=['POST'])
def get_info():
    """Devuelve metadatos del video."""
    data = request.get_json()
    url = data.get('url')
    if not url:
        return jsonify({'error': 'URL requerida'}), 400
    try:
        info = get_video_info(url)
        return jsonify(info)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/download', methods=['POST'])
def download():
    """
    Descarga un video/audio según los parámetros.
    Espera JSON: { "url": "...", "format": "video"|"mp3", "quality": "720p"|"1080p"|"original" }
    """
    data = request.get_json()
    url = data.get('url')
    fmt = data.get('format', 'video')
    quality = data.get('quality', '720p')
    
    if not url:
        return jsonify({'error': 'URL requerida'}), 400
    
    try:
        # Limpiar archivos viejos antes de descargar
        cleanup_old_files(max_age_minutes=30)
        
        if fmt == 'mp3':
            filepath = download_video(url, format_id='mp3')
        else:
            # Mapear calidad a selector
            filepath = download_video(url, quality=quality)
        
        # Enviar archivo y luego eliminarlo (o dejarlo para limpieza futura)
        response = send_file(
            filepath,
            as_attachment=True,
            download_name=filepath.name,
            mimetype='audio/mpeg' if fmt == 'mp3' else 'video/mp4'
        )
        
        # Programar borrado después de enviar (para no dejar archivos)
        @response.call_on_close
        def remove_file():
            try:
                filepath.unlink()
                logger.info(f"Archivo servido y eliminado: {filepath.name}")
            except Exception as e:
                logger.warning(f"No se pudo eliminar {filepath}: {e}")
        
        return response
        
    except Exception as e:
        logger.error(f"Error en descarga: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/health', methods=['GET'])
def health():
    return jsonify({'status': 'ok', 'service': 'VoidDown Backend'})

if __name__ == '__main__':
    print("\n" + "="*50)
    print("🚀 VoidDown Backend iniciado")
    print(f"📁 Archivos temporales en: {DOWNLOAD_DIR}")
    print("🌐 Escuchando en http://localhost:80")
    print("="*50 + "\n")
    app.run(host='0.0.0.0', port=80, debug=True, threaded=True)

