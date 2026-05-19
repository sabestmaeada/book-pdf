#!/usr/bin/env python3
"""
sync_toc.py
อ่าน <h1 class="ch-title"> ในแต่ละ <section class="chapter" id="chapter-N">
แล้วเขียนทับข้อความใน <span class="toc-name"> ของ <a href="#chapter-N"> ใน TOC

Usage:
    python3 sync_toc.py book.html                     # → book.synced.html
    python3 sync_toc.py book.html -o out.html         # → out.html
"""

import argparse
import sys
from pathlib import Path

from bs4 import BeautifulSoup


def sync(html: str) -> tuple[str, list[str], list[str]]:
    soup = BeautifulSoup(html, "html.parser")

    chapters: dict[str, str] = {}
    for section in soup.select("section.chapter[id]"):
        title_el = section.select_one("h1.ch-title")
        if title_el is None:
            continue
        chapters[section["id"]] = title_el.get_text(strip=True)

    updated: list[str] = []
    missing: list[str] = []

    for item in soup.select("a.toc-item[href^='#']"):
        target = item["href"].lstrip("#")
        name_el = item.select_one("span.toc-name")
        if name_el is None:
            continue

        new_title = chapters.get(target)
        if new_title is None:
            missing.append(target)
            continue

        if name_el.get_text(strip=True) != new_title:
            name_el.clear()
            name_el.append(new_title)
            updated.append(target)

    return str(soup), updated, missing


def main() -> int:
    parser = argparse.ArgumentParser(description="Sync TOC names from chapter titles")
    parser.add_argument("input", type=Path, help="Source HTML (e.g. book.html)")
    parser.add_argument(
        "-o", "--output", type=Path,
        help="Output path (default: <input>.synced.html)",
    )
    args = parser.parse_args()

    if not args.input.is_file():
        print(f"error: {args.input} not found", file=sys.stderr)
        return 1

    out_path = args.output or args.input.with_suffix(".synced.html")

    html = args.input.read_text(encoding="utf-8")
    new_html, updated, missing = sync(html)
    out_path.write_text(new_html, encoding="utf-8")

    print(f"wrote: {out_path}")
    print(f"updated {len(updated)} TOC entries")
    for cid in updated:
        print(f"  - #{cid}")

    if missing:
        print(f"warn: {len(missing)} TOC entries have no matching chapter:", file=sys.stderr)
        for cid in missing:
            print(f"  - #{cid}", file=sys.stderr)

    return 0


if __name__ == "__main__":
    sys.exit(main())
