#!/usr/bin/env python3
"""Rendered-layout regression gate for the Fly64 dashboard (Playwright).

Boots a throwaway static server for fly64/web (dashboard markup without the
WSL telemetry), renders the page at several viewports, and fails (exit 1) on:
  G1  horizontal overflow at any viewport
  G2  any zero-size canvas (collapsed chart placeholder)
  G3  in wide mode (>=1400px) the two grid columns must be equal within 5%
  G4  Auto layout mode must match the viewport (single <1400px, wide >=1400px)

Usage:
    python scripts/layout_audit.py [--web-dir DIR] [--port 8791]

Requires: playwright (pip) + chromium (playwright install chromium).
"""

import argparse
import functools
import http.server
import socketserver
import threading
import sys
from pathlib import Path

VIEWPORTS = [(1280, 1050), (1440, 1050), (1680, 1050), (1920, 1050)]

PROBE = """() => ({
  wide: document.body.classList.contains('layout-wide'),
  cols: getComputedStyle(document.querySelector('main')).gridTemplateColumns
          .split(' ').map(parseFloat),
  zeroCanvas: [...document.querySelectorAll('canvas')]
    .filter(c => c.getBoundingClientRect().width === 0
              || c.getBoundingClientRect().height === 0).map(c => c.id),
  hOverflow: document.documentElement.scrollWidth > window.innerWidth,
})"""


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--web-dir", default=str(Path(__file__).resolve().parent.parent / "web"))
    ap.add_argument("--port", type=int, default=8791)
    args = ap.parse_args()
    web = Path(args.web_dir).resolve()

    handler = http.server.SimpleHTTPRequestHandler
    handler.log_message = lambda *a, **k: None  # keep gate output clean
    handler = functools.partial(handler, directory=str(web))
    httpd = socketserver.TCPServer(("127.0.0.1", args.port), handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{args.port}/index.html"

    from playwright.sync_api import sync_playwright

    failures = []
    with sync_playwright() as p:
        browser = p.chromium.launch()
        for w, h in VIEWPORTS:
            pg = browser.new_page(viewport={"width": w, "height": h})
            pg.goto(base, wait_until="load")
            pg.wait_for_timeout(1200)
            r = pg.evaluate(PROBE)
            expect_wide = w >= 1400
            tag = f"[{w}px]"
            if r["hOverflow"]:
                failures.append(f"{tag} G1 horizontal overflow")
            if r["zeroCanvas"]:
                failures.append(f"{tag} G2 zero-size canvas: {r['zeroCanvas']}")
            is_wide = "layout-wide" in (r["wide"] if isinstance(r["wide"], str) else "")
            if r["wide"] != expect_wide:
                failures.append(f"{tag} G4 layout mode mismatch: wide={r['wide']} expected {expect_wide}")
            if expect_wide and len(r["cols"]) == 2:
                a, bcol = r["cols"]
                if abs(a - bcol) / max(a, bcol) > 0.05:
                    failures.append(f"{tag} G3 unequal columns: {a:.0f}/{bcol:.0f}")
            print(f"{tag} wide={r['wide']} cols={[round(c) for c in r['cols']]} "
                  f"zero={r['zeroCanvas']} ovf={r['hOverflow']}")
            pg.close()
        browser.close()
    httpd.shutdown()

    if failures:
        print("\nLAYOUT AUDIT FAILED:")
        for f in failures:
            print("  -", f)
        return 1
    print("\nLayout audit passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
