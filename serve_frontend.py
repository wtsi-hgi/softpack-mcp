#!/usr/bin/env python3
"""
Simple HTTP server to serve the Softpack Recipe Manager frontend.
"""

import http.server
import os
import socketserver
import sys
from pathlib import Path

# Configuration
PORT = 8001
DIRECTORY = Path(__file__).parent


class CustomHTTPRequestHandler(http.server.SimpleHTTPRequestHandler):
    """Custom HTTP request handler with CORS support and proper MIME types."""

    def end_headers(self):
        """Add CORS headers to allow cross-origin requests."""
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, PUT, DELETE, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        super().end_headers()

    def do_OPTIONS(self):
        """Handle preflight OPTIONS requests for CORS."""
        self.send_response(200)
        self.end_headers()

    def guess_type(self, path):
        """Override MIME type guessing for better file serving."""
        if path.endswith(".html"):
            return "text/html"
        elif path.endswith(".js"):
            return "application/javascript"
        elif path.endswith(".css"):
            return "text/css"
        elif path.endswith(".json"):
            return "application/json"
        return super().guess_type(path)

    def do_GET(self):
        """Override GET to inject environment variables into HTML files."""
        if self.path.endswith(".html") or self.path == "/":
            # Handle HTML files with environment variable injection
            file_path = self.translate_path(self.path)
            if self.path == "/":
                file_path = os.path.join(DIRECTORY, "index.html")

            if os.path.exists(file_path):
                try:
                    with open(file_path, encoding="utf-8") as f:
                        content = f.read()

                    # Get API base URL from environment variable
                    api_base_url = os.getenv("API_BASE_URL", "http://localhost:8000")

                    # Replace placeholder with actual API base URL
                    content = content.replace("{{API_BASE_URL}}", api_base_url)

                    # Send the modified content
                    self.send_response(200)
                    self.send_header("Content-Type", "text/html; charset=utf-8")
                    self.end_headers()
                    self.wfile.write(content.encode("utf-8"))
                    return
                except Exception as e:
                    print(f"Error processing HTML file: {e}")

        # Fall back to default behavior for non-HTML files
        super().do_GET()


def main():
    """Start the HTTP server."""
    # Change to the script directory
    os.chdir(DIRECTORY)

    # Get API base URL from environment
    api_base_url = os.getenv("API_BASE_URL", "http://localhost:8000")

    # Create server
    with socketserver.TCPServer(("", PORT), CustomHTTPRequestHandler) as httpd:
        print("🚀 Softpack Frontend Server starting...")
        print(f"   📁 Serving directory: {DIRECTORY}")
        print(f"   🌐 Frontend URL: http://localhost:{PORT}")
        print(f"   🔗 API URL: {api_base_url}")
        print("   ⏹️  Press Ctrl+C to stop the server")
        print()

        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\n🛑 Server stopped by user")
        except Exception as e:
            print(f"\n❌ Server error: {e}")
            sys.exit(1)


if __name__ == "__main__":
    main()
