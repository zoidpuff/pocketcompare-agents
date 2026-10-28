#!/usr/bin/env python
"""Tiny HTTP server that stands in for the GCS bucket in smoke_test.sh (GET <root>/<object name>).

    python afdb/mock_gcs_server.py DIR --port-file port.txt [--truncate-first BYTES]

``--truncate-first N``: the first GET of every object larger than N bytes is cut after N bytes (connection
closed), to exercise the worker's restart-and-skip download path. Binds to 127.0.0.1 on a free port.
"""
import argparse
import http.server
import os
import threading
from pathlib import Path

SEEN: set = set()
LOCK = threading.Lock()


def handler(root: Path, cut: int):
    class H(http.server.BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def do_GET(self):  # noqa: N802
            from urllib.parse import unquote, urlparse
            p = (root / unquote(urlparse(self.path).path).lstrip("/")).resolve()
            if root not in p.parents or not p.is_file():
                self.send_error(404)
                return
            size = p.stat().st_size
            with LOCK:
                first = p not in SEEN
                SEEN.add(p)
            n = cut if (cut and first and size > cut) else size
            self.send_response(200)
            self.send_header("Content-Length", str(size))
            self.send_header("Content-Type", "application/octet-stream")
            self.end_headers()
            with open(p, "rb") as fh:
                left = n
                while left > 0:
                    b = fh.read(min(1 << 20, left))
                    if not b:
                        break
                    self.wfile.write(b)
                    left -= len(b)
            if n < size:
                self.close_connection = True
    return H


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("root")
    ap.add_argument("--port-file", required=True)
    ap.add_argument("--truncate-first", type=int, default=0)
    a = ap.parse_args()
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler(Path(a.root).resolve(), a.truncate_first))
    tmp = a.port_file + ".tmp"
    Path(tmp).write_text(str(srv.server_address[1]))
    os.replace(tmp, a.port_file)
    srv.serve_forever()


if __name__ == "__main__":
    main()
