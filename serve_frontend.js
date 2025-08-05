#!/usr/bin/env node
/**
 * Node.js HTTP server to serve the Softpack Recipe Manager frontend.
 */

const express = require('express');
const cors = require('cors');
const fs = require('fs');
const path = require('path');

// Configuration
const PORT = parseInt(process.env.SOFTPACK_PORT) || 80;
const DIRECTORY = __dirname;

// Create Express app
const app = express();

// Enable CORS with proper headers
app.use(cors({
    origin: '*',
    methods: ['GET', 'POST', 'PUT', 'DELETE', 'OPTIONS'],
    allowedHeaders: ['Content-Type']
}));

// Custom middleware to handle HTML files with environment variable injection
app.use((req, res, next) => {
    // Handle HTML files and root path
    if (req.path.endsWith('.html') || req.path === '/') {
        let filePath;
        if (req.path === '/') {
            filePath = path.join(DIRECTORY, 'index.html');
        } else {
            filePath = path.join(DIRECTORY, req.path);
        }

        // Check if the HTML file exists
        if (fs.existsSync(filePath)) {
            try {
                let content = fs.readFileSync(filePath, 'utf8');

                // Get API base URL from environment variable
                const apiBaseUrl = process.env.API_BASE_URL || 'http://localhost:8000';
                console.log(`API base URL: ${apiBaseUrl}`);

                // Replace placeholder with actual API base URL
                content = content.replace(/\{\{API_BASE_URL\}\}/g, apiBaseUrl);

                // Send the modified content
                res.setHeader('Content-Type', 'text/html; charset=utf-8');
                res.send(content);
                return;
            } catch (error) {
                console.error(`Error processing HTML file: ${error}`);
                // Fall through to default behavior
            }
        }
    }

    // Continue to next middleware for non-HTML files
    next();
});

// Serve static files from the current directory
app.use(express.static(DIRECTORY, {
    // Set proper MIME types
    setHeaders: (res, path) => {
        if (path.endsWith('.js')) {
            res.setHeader('Content-Type', 'application/javascript');
        } else if (path.endsWith('.css')) {
            res.setHeader('Content-Type', 'text/css');
        } else if (path.endsWith('.json')) {
            res.setHeader('Content-Type', 'application/json');
        }
    }
}));

// Handle 404 for missing files
app.use((req, res) => {
    res.status(404).send('Not Found');
});

// Start the server
function main() {
    // Change to the script directory
    process.chdir(__dirname);

    // Get API base URL from environment
    const apiBaseUrl = process.env.API_BASE_URL || 'http://localhost:8000';

    const server = app.listen(PORT, '0.0.0.0', () => {
        console.log('🚀 Softpack Frontend Server starting...');
        console.log(`   📁 Serving directory: ${DIRECTORY}`);
        console.log(`   🌐 Frontend URL: http://localhost:${PORT}`);
        console.log(`   🔗 API URL: ${apiBaseUrl}`);
        console.log('   ⏹️  Press Ctrl+C to stop the server');
        console.log('');
    });

    // Handle graceful shutdown
    process.on('SIGINT', () => {
        console.log('\n🛑 Server stopped by user');
        server.close(() => {
            process.exit(0);
        });
    });

    process.on('SIGTERM', () => {
        console.log('\n🛑 Server stopped by system');
        server.close(() => {
            process.exit(0);
        });
    });

    // Handle server errors
    server.on('error', (error) => {
        console.error(`\n❌ Server error: ${error}`);
        process.exit(1);
    });
}

if (require.main === module) {
    main();
}

module.exports = app;
