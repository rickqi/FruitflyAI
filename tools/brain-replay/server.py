#!/usr/bin/env python3
"""Zero-dependency static server for the Fly64 brain decision replay browser.

Run:  python server.py   ->  http://127.0.0.1:8787/
Re-export data any time: python export_trace.py  (or GET /api/export)
"""
from __future__ import annotations

import json
import subprocess
import sys
from http.server import HTTPServer, SimpleHTTPRequestHandler
from pathlib import Path

HERE = Path(__file__).resolve().parent
WEB = HERE / "web"
PORT = 8787


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *a, **kw):
        super().__init__(*a, directory=str(WEB), **kw)

    def send_json(self, obj, code=200):
        body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path == "/api/trace":
            p = WEB / "trace.json"
            if not p.exists():
                self.send_json({"error": "trace.json missing; run export_trace.py"}, 404)
                return
            return super().do_GET()  # serve the file as-is
        if self.path == "/api/export":
            r = subprocess.run(
                [sys.executable, str(HERE / "export_trace.py")],
                capture_output=True, text=True,
            )
            self.send_json({"ok": r.returncode == 0, "stdout": r.stdout, "stderr": r.stderr})
            return
        return super().do_GET()

    def log_message(self, fmt, *args):
        pass


if __name__ == "__main__":
    print(f"Fly64 brain replay browser -> http://127.0.0.1:{PORT}/")
    HTTPServer(("127.0.0.1", PORT), Handler).serve_forever()
