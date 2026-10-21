#!/usr/bin/env python3
"""Download Fraunces and Inter (latin subset, woff2) from Google Fonts.

Files go to showcase/fonts/ with a manifest. build_showcase.py embeds them
as base64 so the page works offline. Both fonts use the SIL Open Font License.

Usage:
    python showcase/fetch_fonts.py
"""
from __future__ import annotations

import json
import re
import sys
import urllib.request
from pathlib import Path

FONTS_DIR = Path(__file__).resolve().parent / "fonts"
MANIFEST = FONTS_DIR / "fonts.json"
CSS_URL = ("https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,600;9..144,700"
           "&family=Inter:wght@400;600;700&display=swap")
# Google serves woff2 only to modern browsers.
USER_AGENT = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
              "(KHTML, like Gecko) Chrome/124.0 Safari/537.36")
BLOCK = re.compile(r"/\*\s*([\w-]+)\s*\*/\s*@font-face\s*{(.*?)}", re.S)


def _get(url: str) -> bytes:
    if not url.startswith("https://fonts.g"):
        raise ValueError(f"Refusing to fetch from an unexpected host: {url}")
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return resp.read()


def fetch() -> list[dict]:
    css = _get(CSS_URL).decode("utf-8")
    FONTS_DIR.mkdir(parents=True, exist_ok=True)
    entries, seen = [], {}
    for subset, body in BLOCK.findall(css):
        if subset != "latin":
            continue
        family = re.search(r"font-family:\s*'([^']+)'", body).group(1)
        weight = re.search(r"font-weight:\s*([\d ]+);", body).group(1).strip()
        style = re.search(r"font-style:\s*(\w+);", body).group(1)
        url = re.search(r"url\((https://[^)]+\.woff2)\)", body).group(1)
        if url not in seen:
            name = f"{family.lower()}_{len(seen)}.woff2"
            (FONTS_DIR / name).write_bytes(_get(url))
            seen[url] = name
        entries.append({"family": family, "weight": weight, "style": style, "file": seen[url]})
    if not entries:
        raise RuntimeError("No latin font files found in the Google Fonts CSS")
    MANIFEST.write_text(json.dumps(entries, indent=2), encoding="utf-8")
    return entries


def main() -> int:
    try:
        entries = fetch()
    except Exception as exc:  # network errors vary by platform
        print(f"Error: could not fetch fonts: {exc}", file=sys.stderr)
        return 1
    for e in entries:
        print(f"{e['family']} {e['weight']} {e['style']}: {e['file']}")
    print(f"Manifest written to {MANIFEST}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
