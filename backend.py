"""
VoidDown Backend Unificado (Frontend + API) con máxima protección anti-bloqueo
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

# Configurar logging para que salga en los logs de Back4app
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = Flask(__name__, static_folder='frontend', static_url_path='')
CORS(app)

DOWNLOAD_DIR = Path(tempfile.gettempdir()) / "voiddown_downloads"
DOWNLOAD_DIR.mkdir(exist_ok=True)

# --- Manejo de cookies desde variable de entorno ---
cookies_content = os.environ.get('YOUTUBE_COOKIES', '')
cookies_path = None
if cookies_content:
    with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
        f.write(cookies_content)
        cookies_path = f.name
    logger.info("Cookies cargadas desde variable de entorno")
else:
    if Path('cookies.txt').exists():
        cookies_path = 'cookies.txt'
        logger.info("Usando archivo cookies.txt local")
    else:
        logger.warning("No se encontraron cookies. Algunos videos podrían fallar.")

# --- Opciones base ULTRA reforzadas contra bloqueos ---
BASE_OPTS = {
    'quiet': True,
    'no_warnings': True,
    'extract_flat': False,
    'noplaylist': True,
    'socket_timeout': 60,
    'retries': 10,
    'fragment_retries': 10,
    'extractor_retries': 5,
    'file_access_retries': 5,
    'geo_bypass': True,
    'geo_bypass_country': 'US',
    'concurrent_fragment_downloads': 2,          # Menos concurrencia = menos detección
    'buffersize': 1024 * 1024,
    'force_ipv4': True,
    'cookiefile': cookies_path if cookies_path else None,
    'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36',
    'http_headers': {
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'en-us,en;q=0.5',
        'Sec-Fetch-Mode': 'navigate',
        'Sec-Fetch-Site': 'none',
    },
    'extractor_args': {
        'youtube': {
            'player_client': ['android', 'ios', 'web'],
            'player_skip': ['configs', 'webpage'],
            'skip': ['dash', 'hls'],
        }
    },
    # Pequeña pausa entre fragmentos y solicitudes
    'sleep_interval': 2,
    'max_sleep_interval': 5,
    'sleep_interval_requests': 1,
}

# ----- Servir el frontend -----
@app.route('/')
def serve_index():
    return send_from_directory('frontend', 'index.html')

@app.route('/<path:path>')
def serve_static(path):
    return send_from_directory('frontend', path)

# ----- Endpoints de la API -----
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
    logger.info("Recibida señal de terminación. Cerrando...")
    if cookies_path and cookies_path != 'cookies.txt' and Path(cookies_path).exists():
        Path(cookies_path).unlink()
    exit(0)

signal.signal(signal.SIGTERM, handle_sigterm)
signal.signal(signal.SIGINT, handle_sigterm)

if __name__ == '__main__':
    logger.info("="*50)
    logger.info("🚀 VoidDown Backend + Frontend unificados")
    logger.info(f"📁 Archivos temporales en: {DOWNLOAD_DIR}")
    logger.info("🌐 Escuchando en http://0.0.0.0:80")
    logger.info("="*50)
    app.run(host='0.0.0.0', port=80, debug=False, threaded=True)
