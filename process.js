const express = require('express');
const path = require('path');
const fs = require('fs');
const { runPython } = require('../utils/runner');

module.exports = function(outputsDir) {
    const router = express.Router();

    // Process endpoint
    router.post('/process', async (req, res) => {
        try {
            const { filePath } = req.body;

            if (!filePath) {
                return res.status(400).json({ error: 'No file path provided' });
            }

            if (!fs.existsSync(filePath)) {
                return res.status(400).json({ error: 'Uploaded file not found: ' + filePath });
            }

            const outputFileName = `organized_${Date.now()}.pdf`;
            const outputPath = path.join(outputsDir, outputFileName);

            // Run Python script to process the PDF
            const result = await runPython(filePath, outputPath);

            res.json({
                success: true,
                outputPath: outputPath,
                outputFileName: outputFileName,
                stats: result.stats || {}
            });

        } catch (error) {
            console.error('Process error:', error);
            res.status(500).json({
                error: 'Processing failed',
                details: error.message
            });
        }
    });

    // Download endpoint
    router.get('/download/:filename', (req, res) => {
        try {
            const fileName = req.params.filename;
            // Sanitize filename - no path traversal
            const safeName = path.basename(fileName);
            const filePath = path.join(outputsDir, safeName);

            if (!fs.existsSync(filePath)) {
                return res.status(404).json({ error: 'File not found' });
            }

            res.download(filePath);
        } catch (error) {
            res.status(500).json({ error: error.message });
        }
    });

    return router;
};
