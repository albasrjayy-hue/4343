/**
 * app.js  –  Delivery Organizer Server
 * Zero npm dependencies: uses only Node.js built-ins (http, fs, path, crypto)
 * Run from project root: node server/app.js
 */

'use strict';

const http = require('http');
const fs = require('fs');
const path = require('path');
const crypto = require('crypto');
const { runPython } = require('./utils/runner');

const PORT = process.env.PORT || 3000;

const ROOT = path.join(__dirname, '..');
const UPLOADS_DIR = path.join(ROOT, 'uploads');
const OUTPUTS_DIR = path.join(ROOT, 'outputs');
const PUBLIC_DIR  = path.join(ROOT, 'public');

[UPLOADS_DIR, OUTPUTS_DIR].forEach(d => {
    if (!fs.existsSync(d)) fs.mkdirSync(d, { recursive: true });
});

const MIME = {
    '.html': 'text/html; charset=utf-8',
    '.css':  'text/css',
    '.js':   'application/javascript',
    '.ico':  'image/x-icon',
    '.png':  'image/png',
};

function parseMultipart(req) {
    return new Promise((resolve, reject) => {
        const ct = req.headers['content-type'] || '';
        const boundaryMatch = ct.match(/boundary=(.+)/);
        if (!boundaryMatch) return reject(new Error('No boundary in multipart'));
        const boundary = '--' + boundaryMatch[1];

        const chunks = [];
        req.on('data', c => chunks.push(c));
        req.on('end', () => {
            try {
                const buf = Buffer.concat(chunks);
                const sep = Buffer.from('\r\n' + boundary);
                const start = Buffer.from(boundary + '\r\n');

                let pos = buf.indexOf(start);
                if (pos === -1) return reject(new Error('Multipart parse error'));
                pos += start.length;

                const headEnd = buf.indexOf(Buffer.from('\r\n\r\n'), pos);
                if (headEnd === -1) return reject(new Error('Multipart header error'));
                const headers = buf.slice(pos, headEnd).toString();

                const nameMatch = headers.match(/name="([^"]+)"/);
                const fileMatch = headers.match(/filename="([^"]+)"/);
                const mimeMatch = headers.match(/Content-Type:\s*(\S+)/i);

                const dataStart = headEnd + 4;
                const dataEnd = buf.indexOf(sep, dataStart);
                if (dataEnd === -1) return reject(new Error('Multipart data boundary not found'));

                const data = buf.slice(dataStart, dataEnd);
                resolve({
                    fieldname: nameMatch ? nameMatch[1] : '',
                    originalname: fileMatch ? fileMatch[1] : 'upload.pdf',
                    mimetype: mimeMatch ? mimeMatch[1] : 'application/octet-stream',
                    buffer: data,
                    size: data.length,
                });
            } catch (e) { reject(e); }
        });
        req.on('error', reject);
    });
}

function readJSON(req) {
    return new Promise((resolve, reject) => {
        let body = '';
        req.on('data', c => body += c);
        req.on('end', () => {
            try { resolve(JSON.parse(body)); }
            catch (e) { reject(new Error('Invalid JSON')); }
        });
        req.on('error', reject);
    });
}

function sendJSON(res, code, obj) {
    const body = JSON.stringify(obj);
    res.writeHead(code, { 'Content-Type': 'application/json', 'Content-Length': Buffer.byteLength(body) });
    res.end(body);
}

function sendError(res, code, msg) {
    sendJSON(res, code, { success: false, error: msg });
}

function serveStatic(res, filePath) {
    if (!fs.existsSync(filePath)) { res.writeHead(404); res.end('Not found'); return; }
    const ext = path.extname(filePath).toLowerCase();
    const mime = MIME[ext] || 'application/octet-stream';
    const stat = fs.statSync(filePath);
    res.writeHead(200, { 'Content-Type': mime, 'Content-Length': stat.size });
    fs.createReadStream(filePath).pipe(res);
}

const server = http.createServer(async (req, res) => {
    const url = new URL(req.url, `http://localhost:${PORT}`);
    const pathname = url.pathname;
    const method = req.method;

    try {
        if (method === 'GET' && (pathname === '/' || pathname === '/index.html')) {
            return serveStatic(res, path.join(PUBLIC_DIR, 'index.html'));
        }

        if (method === 'GET' && (pathname.endsWith('.css') || pathname.endsWith('.js') || pathname.endsWith('.ico'))) {
            const safe = path.normalize(pathname).replace(/^(\.\.[\/\\])+/, '');
            return serveStatic(res, path.join(PUBLIC_DIR, safe));
        }

        if (method === 'GET' && pathname === '/api/health') {
            return sendJSON(res, 200, { status: 'ok', timestamp: new Date().toISOString() });
        }

        if (method === 'POST' && pathname === '/api/upload') {
            const ct = req.headers['content-type'] || '';
            if (!ct.includes('multipart/form-data')) return sendError(res, 400, 'Expected multipart/form-data');

            const file = await parseMultipart(req);

            if (file.mimetype !== 'application/pdf' && !file.originalname.toLowerCase().endsWith('.pdf')) {
                return sendError(res, 400, 'Only PDF files are allowed');
            }
            if (file.size > 50 * 1024 * 1024) return sendError(res, 400, 'File too large (max 50MB)');

            const uniqueName = `upload_${Date.now()}_${crypto.randomBytes(4).toString('hex')}_${path.basename(file.originalname)}`;
            const filePath = path.join(UPLOADS_DIR, uniqueName);
            fs.writeFileSync(filePath, file.buffer);

            return sendJSON(res, 200, { success: true, filePath, fileName: uniqueName });
        }

        if (method === 'POST' && pathname === '/api/process') {
            const body = await readJSON(req);
            const { filePath } = body;
            if (!filePath) return sendError(res, 400, 'No file path provided');
            if (!fs.existsSync(filePath)) return sendError(res, 400, 'Uploaded file not found');

            const outputFileName = `organized_${Date.now()}.pdf`;
            const outputPath = path.join(OUTPUTS_DIR, outputFileName);
            const result = await runPython(filePath, outputPath);

            return sendJSON(res, 200, { success: true, outputPath, outputFileName, stats: result.stats || {} });
        }

        if (method === 'GET' && pathname.startsWith('/api/download/')) {
            const safeName = path.basename(pathname.slice('/api/download/'.length));
            const filePath = path.join(OUTPUTS_DIR, safeName);
            if (!fs.existsSync(filePath)) return sendError(res, 404, 'File not found');
            const stat = fs.statSync(filePath);
            res.writeHead(200, {
                'Content-Type': 'application/pdf',
                'Content-Disposition': `attachment; filename="${safeName}"`,
                'Content-Length': stat.size,
            });
            return fs.createReadStream(filePath).pipe(res);
        }

        sendError(res, 404, 'Not found');

    } catch (err) {
        console.error('[server error]', err);
        try { sendError(res, 500, err.message); } catch (_) { res.end(); }
    }
});

server.listen(PORT, '0.0.0.0', () => {
    console.log('\n✅ Delivery Organizer running on http://localhost:' + PORT);
    console.log('   Uploads : ' + UPLOADS_DIR);
    console.log('   Outputs : ' + OUTPUTS_DIR + '\n');
});
