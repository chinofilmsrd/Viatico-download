const express = require('express');
const cors = require('cors');
const { execFile } = require('child_process');
const util = require('util');
const fs = require('fs');
const path = require('path');
const os = require('os');

const execFileAsync = util.promisify(execFile);

const app = express();
const PORT = process.env.PORT || 5001;

// Comando para ejecutar yt-dlp según el sistema operativo
const ytDlpCmd = os.platform() === 'win32' ? './yt-dlp.exe' : 'yt-dlp';

// Carpeta temporal para descargas
const TEMP_DIR = path.join(__dirname, 'temp');
if (!fs.existsSync(TEMP_DIR)) {
    fs.mkdirSync(TEMP_DIR);
}

// Middlewares
app.use(cors());
app.use(express.json());
app.use(express.static(__dirname)); // Sirve el index.html automáticamente

// Limpiar archivos temporales antiguos al iniciar
fs.readdir(TEMP_DIR, (err, files) => {
    if (err) return;
    for (const file of files) {
        fs.unlink(path.join(TEMP_DIR, file), err => {});
    }
});

// Endpoint para obtener información del video
app.post('/info', async (req, res) => {
    try {
        const { url } = req.body;
        if (!url) return res.status(400).json({ error: 'Falta la URL' });
        
        // yt-dlp (exe en Windows, global en Linux)
        const { stdout } = await execFileAsync(ytDlpCmd, ['--dump-json', url], { maxBuffer: 10 * 1024 * 1024 });
        const info = JSON.parse(stdout);
        
        res.json({
            title: info.title,
            uploader: info.uploader || info.channel,
            duration: info.duration,
            thumbnail: info.thumbnail
        });
    } catch (error) {
        console.error('Error en /info:', error.message);
        res.status(500).json({ error: `Error: ${error.message}` });
    }
});

// Endpoint para descargar
app.post('/download', async (req, res) => {
    const id = Date.now() + '-' + Math.round(Math.random() * 10000);
    let finalPath = '';
    
    try {
        const { url, format, quality } = req.body;
        if (!url) return res.status(400).json({ error: 'Falta la URL' });

        let args = [];
        let expectedExt = '';
        
        // Obtener el título rápido
        const { stdout: titleOut } = await execFileAsync(ytDlpCmd, ['--get-title', url]);
        const title = titleOut.trim().replace(/[^\w\s]/gi, '_') || 'video';

        if (format === 'mp3') {
            const filenameTemplate = path.join(TEMP_DIR, `${id}.%(ext)s`);
            args = [
                '-x', '--audio-format', 'mp3',
                '-o', filenameTemplate,
                url
            ];
            expectedExt = 'mp3';
            finalPath = path.join(TEMP_DIR, `${id}.mp3`);
        } else {
            const filenameTemplate = path.join(TEMP_DIR, `${id}.%(ext)s`);
            let formatQuery = 'bestvideo+bestaudio/best';
            
            if (quality === '1080p') {
                formatQuery = 'bestvideo[height<=1080]+bestaudio/best';
            } else if (quality === '720p') {
                formatQuery = 'bestvideo[height<=720]+bestaudio/best';
            }
            
            args = [
                '-f', formatQuery,
                '--merge-output-format', 'mp4',
                '-o', filenameTemplate,
                url
            ];
            expectedExt = 'mp4';
            finalPath = path.join(TEMP_DIR, `${id}.mp4`);
        }
        
        // Ejecutar descarga
        await execFileAsync(ytDlpCmd, args);
        
        // Enviar al cliente
        res.download(finalPath, `${title}.${expectedExt}`, (err) => {
            // Borrar archivo temporal después de enviarlo
            if (fs.existsSync(finalPath)) {
                fs.unlinkSync(finalPath);
            }
        });

    } catch (error) {
        console.error('Error en /download:', error.message);
        if (fs.existsSync(finalPath)) {
            fs.unlinkSync(finalPath);
        }
        if (!res.headersSent) {
            res.status(500).json({ error: 'Error procesando la descarga.' });
        }
    }
});

app.listen(PORT, () => {
    console.log(`Backend funcionando en http://localhost:${PORT}`);
    console.log('Esperando peticiones (usando yt-dlp)...');
});
