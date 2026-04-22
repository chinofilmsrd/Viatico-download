"""
VoidDown Backend para Render con máxima protección anti-bloqueo
"""
import os
import re
import time
import tempfile
import logging
import signal
from pathlib import Path
from flask import Flask, request, send_file, jsonify, send_from_directory
from flask_cors import CORS
import yt_dlp

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = Flask(__name__, static_folder='frontend', static_url_path='')
CORS(app)

DOWNLOAD_DIR = Path(tempfile.gettempdir()) / "voiddown_downloads"
DOWNLOAD_DIR.mkdir(exist_ok=True)

# --- Manejo robusto de cookies desde variable de entorno ---
def setup_cookies():
    cookies_content = os.environ.get('YOUTUBE_COOKIES', '')
    if not cookies_content:
        if Path('cookies.txt').exists():
            logger.info("Usando cookies.txt local")
            return 'cookies.txt'
        logger.warning("No se encontraron cookies. Algunos videos pueden fallar.")
        return None

    # Limpiar y formatear contenido
    cookies_content = cookies_content.replace('\\n', '\n').replace('\r\n', '\n')
    with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
        f.write(cookies_content)
        cookies_path = f.name
    logger.info(f"Cookies cargadas desde variable de entorno en {cookies_path}")
    return cookies_path

cookies_path = setup_cookies()

# --- Opciones base optimizadas para cliente móvil (menos bloqueos) ---
BASE_OPTS = {
    'quiet': True,
    'no_warnings': True,
    'extract_flat': False,
    'noplaylist': True,
    'socket_timeout': 60,
    'retries': 5,
    'fragment_retries': 5,
    'geo_bypass': True,
    'geo_bypass_country': 'US',
    'concurrent_fragment_downloads': 2,
    'buffersize': 1024 * 1024,
    'force_ipv4': True,
    'cookiefile': cookies_path,
    # Cliente Android: menos probabilidades de bloqueo
    'user_agent': 'com.google.android.youtube/19.09.37 (Linux; U; Android 13; en_US; Pixel 7)',
    'extractor_args': {
        'youtube': {
            'player_client': ['android', 'web'],
            'skip': ['dash', 'hls', 'webpage'],
        }
    },
    'sleep_interval': 2,
    'max_sleep_interval': 5,
    'sleep_interval_requests': 1,
}

# ----- Servir frontend (opcional, Render puede servir el backend y frontend juntos) -----
@app.route('/')
def serve_index():
    return send_from_directory('frontend', 'index.html')

@app.route('/<path:path>')
def serve_static(path):
    return send_from_directory('frontend', path)

# ----- Endpoints API -----
@app.route('/health', methods=['GET'])
def health():
    return jsonify({'status': 'ok', 'service': 'VoidDown Backend'})

@app.route('/info', methods=['POST'])
def get_info():
    data = request.get_json()
    url = data.get('url')
    if not url:
        return jsonify({'error': 'URL requerida'}), 400
    try:
        info = extract_video_info(url)
        return jsonify(info)
    except Exception as e:
        logger.exception("Error en /info")
        return jsonify({'error': str(e)}), 500

@app.route('/download', methods=['POST'])
def download():
    data = request.get_json()
    url = data.get('url')
    fmt = data.get('format', 'video')
    quality = data.get('quality', '720p')
    if not url:
        return jsonify({'error': 'URL requerida'}), 400
    try:
        cleanup_old_files(max_age_minutes=30)
        if fmt == 'mp3':
            filepath = download_video(url, format_id='mp3')
        else:
            filepath = download_video(url, quality=quality)
        response = send_file(
            filepath,
            as_attachment=True,
            download_name=filepath.name,
            mimetype='audio/mpeg' if fmt == 'mp3' else 'video/mp4'
        )
        @response.call_on_close
        def remove_file():
            try:
                filepath.unlink()
                logger.info(f"Archivo eliminado: {filepath.name}")
            except Exception as e:
                logger.warning(f"No se pudo eliminar {filepath}: {e}")
        return response
    except Exception as e:
        logger.exception("Error en /download")
        return jsonify({'error': str(e)}), 500

def extract_video_info(url):
    ydl_opts = {**BASE_OPTS, 'skip_download': True, 'quiet': True}
    logger.info(f"Extrayendo info de: {url} con cookiefile={ydl_opts.get('cookiefile')}")
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=False)
        return {
            'id': info.get('id'),
            'title': info.get('title', 'Sin título'),
            'thumbnail': info.get('thumbnail', ''),
            'duration': info.get('duration', 0),
            'uploader': info.get('uploader', 'Desconocido'),
        }

def download_video(url, format_id=None, quality='720p'):
    output_template = str(DOWNLOAD_DIR / '%(title)s.%(ext)s')
    ydl_opts = {
        **BASE_OPTS,
        'outtmpl': output_template,
        'restrictfilenames': True,
    }
    if format_id == 'mp3':
        ydl_opts['format'] = 'bestaudio/best'
        ydl_opts['postprocessors'] = [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '192',
        }]
    else:
        height = quality.replace('p', '') if quality != 'original' else ''
        if height:
            ydl_opts['format'] = f'bestvideo[height<={height}]+bestaudio/best[height<={height}]/best'
        else:
            ydl_opts['format'] = 'bestvideo+bestaudio/best'

    logger.info(f"Iniciando descarga: {url} con cookiefile={ydl_opts.get('cookiefile')}")
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)
        filename = ydl.prepare_filename(info)
        if format_id == 'mp3':
            filename = str(Path(filename).with_suffix('.mp3'))
        filepath = Path(filename)
        if not filepath.exists():
            possible = list(DOWNLOAD_DIR.glob(f"{info.get('title')}*.mp3"))
            if possible:
                filepath = possible[0]
            else:
                raise FileNotFoundError("Archivo no encontrado después de descarga")
        logger.info(f"Descarga completada: {filepath}")
        return filepath

def cleanup_old_files(max_age_minutes=60):
    now = time.time()
    for f in DOWNLOAD_DIR.glob('*'):
        if f.is_file() and (now - f.stat().st_mtime) > (max_age_minutes * 60):
            try:
                f.unlink()
                logger.info(f"Limpieza: {f.name}")
            except Exception as e:
                logger.warning(f"No se pudo eliminar {f}: {e}")

def handle_sigterm(*args):
    logger.info("Cerrando...")
    if cookies_path and cookies_path != 'cookies.txt' and Path(cookies_path).exists():
        Path(cookies_path).unlink()
    exit(0)

signal.signal(signal.SIGTERM, handle_sigterm)
signal.signal(signal.SIGINT, handle_sigterm)

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 10000))
    logger.info("="*50)
    logger.info("🚀 VoidDown Backend para Render")
    logger.info(f"📁 Archivos temporales: {DOWNLOAD_DIR}")
    logger.info(f"🌐 Puerto: {port}")
    logger.info("="*50)
    app.run(host='0.0.0.0', port=port, debug=False, threaded=True)

# ... (todos tus imports anteriores)
from yt_dlp_plugins.extractor import pot_provider

# ... (código de setup_cookies, etc.)

BASE_OPTS = {
    # ... (el resto de tus opciones)
    'extractor_args': {
        'youtube': {
            'player_client': ['android', 'ios', 'web'],
            'skip': ['dash', 'hls'],
            # --- Línea clave para el PO Token ---
            'po_token': pot_provider.get_pot(),
        }
    },
    # ... (más opciones)
}
