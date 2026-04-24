const { spawn } = require('child_process');
const path = require('path');

/**
 * Runs the Python PDF processing script.
 * Path: project/python/generate_pdf.py
 * Called from: project/server/utils/runner.js
 * So: path.join(__dirname, '../../python/generate_pdf.py')
 */
function runPython(inputPath, outputPath) {
    return new Promise((resolve, reject) => {
        // __dirname = project/server/utils
        // ../../python = project/python
        const scriptPath = path.join(__dirname, '../../python/generate_pdf.py');

        console.log(`[runner] Script: ${scriptPath}`);
        console.log(`[runner] Input:  ${inputPath}`);
        console.log(`[runner] Output: ${outputPath}`);

        if (!require('fs').existsSync(scriptPath)) {
            return reject(new Error(`Python script not found: ${scriptPath}`));
        }

        const proc = spawn('python3', [scriptPath, inputPath, outputPath], {
            // Run from project root so relative paths inside Python work too
            cwd: path.join(__dirname, '../..')
        });

        let stdout = '';
        let stderr = '';

        proc.stdout.on('data', (data) => {
            stdout += data.toString();
            console.log('[python]', data.toString().trim());
        });

        proc.stderr.on('data', (data) => {
            stderr += data.toString();
            console.error('[python:err]', data.toString().trim());
        });

        proc.on('close', (code) => {
            if (code !== 0) {
                return reject(new Error(`Python exited with code ${code}:\n${stderr}`));
            }

            // Try to parse JSON stats from last line of stdout
            let stats = {};
            try {
                const lines = stdout.trim().split('\n');
                const lastLine = lines[lines.length - 1];
                stats = JSON.parse(lastLine);
            } catch (_) {
                // Stats are optional
            }

            resolve({ stats });
        });

        proc.on('error', (err) => {
            reject(new Error(`Failed to start Python: ${err.message}`));
        });
    });
}

module.exports = { runPython };
