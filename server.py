"""
Lightweight local development server for Tigran Solomon's Paper Archive.
Runs an HTTP server on http://localhost:8000 and automatically opens the browser.
"""

import os
import sys
import webbrowser
from http.server import HTTPServer, SimpleHTTPRequestHandler
from pathlib import Path

PORT = 8000
DIRECTORY = Path(__file__).parent


class ArchiveHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(DIRECTORY), **kwargs)

    def log_message(self, format, *args):
        # Clean logging
        sys.stdout.write(f"[{self.log_date_time_string()}] {format % args}\n")


def run_server():
    server_address = ("", PORT)
    httpd = HTTPServer(server_address, ArchiveHandler)
    url = f"http://localhost:{PORT}/index.html"
    print("=" * 65)
    print(f"  TIGRAN SOLOMON'S PAPER ARCHIVE // WEB STUDIO")
    print("=" * 65)
    print(f"[+] Server started successfully on: {url}")
    print("[+] Press Ctrl+C to stop the server.")
    print("=" * 65)

    try:
        webbrowser.open(url)
    except Exception:
        pass

    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n[*] Server stopped.")
        httpd.server_close()


if __name__ == "__main__":
    run_server()
