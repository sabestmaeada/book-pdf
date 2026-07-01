#!/usr/bin/env python3
"""
sync_toc.py
1) อ่าน <h1 class="ch-title"> ในแต่ละ <section class="chapter" id="chapter-N">
   แล้วเขียนทับข้อความใน <span class="toc-name"> ของ <a href="#chapter-N"> ใน TOC
2) (default) สร้างสารบัญย่อยระดับ h2 อัตโนมัติ:
   - ใส่ id ให้ h2 ในเนื้อหาบท (ถ้ายังไม่มี) เป็น "<chapter-id>-sN"
   - แทรก <a class="toc-item toc-h2 toc-auto" href="#..."> ใต้บทนั้นใน TOC
   - เลขหน้ามาจาก CSS target-counter เดิม (a.toc-item::after) ไม่ต้องแก้
   idempotent: ลบ toc-auto เดิมทิ้งก่อนสร้างใหม่ทุกครั้ง

Usage:
    python3 sync_toc.py book.html                     # → book.synced.html (มี sub-TOC)
    python3 sync_toc.py book.html -o out.html
    python3 sync_toc.py book.html --no-sub            # เฉพาะ sync ชื่อบท (พฤติกรรมเก่า)
"""

import argparse
import sys
from pathlib import Path

from bs4 import BeautifulSoup


def add_sub_toc(soup: BeautifulSoup) -> int:
    """แทรกสารบัญย่อยระดับ h2 ใต้แต่ละบทใน TOC (return จำนวนที่เพิ่ม)."""
    # ลบ toc-auto เดิม (idempotent)
    for a in soup.select("a.toc-item.toc-auto"):
        a.decompose()

    added = 0
    for section in soup.select("section.chapter[id]"):
        cid = section["id"]
        toc_item = soup.select_one(f'a.toc-item[href="#{cid}"]')
        if toc_item is None:
            continue  # บทนี้ไม่มีบรรทัดใน TOC → ข้าม

        anchor = toc_item
        created: list = []
        idx = 0
        for h2 in section.find_all("h2"):
            text = h2.get_text(" ", strip=True)
            if not text:
                continue
            idx += 1
            hid = h2.get("id")
            if not hid:
                hid = f"{cid}-s{idx}"
                h2["id"] = hid

            a = soup.new_tag("a", href=f"#{hid}")
            a["class"] = ["toc-item", "toc-h2", "toc-auto"]
            span = soup.new_tag("span")
            span["class"] = ["toc-name"]
            span.string = text
            a.append(span)

            anchor.insert_after(a)
            anchor.insert_after("\n    ")  # ขึ้นบรรทัดใหม่ให้อ่านง่าย
            anchor = a
            created.append(a)
            added += 1

        # mark ตัวแรก/สุดท้ายของบท → คุม orphan (บท+h2 ≥2 ท้ายหน้า) / widow (h2 สุดท้ายไม่โดดหัวหน้า) ใน CSS
        if created:
            created[-1]["class"].append("toc-h2-last")
            if len(created) >= 2:                    # mark first เฉพาะเมื่อมี ≥2 (กัน over-glue บทที่มี h2 เดียว)
                created[0]["class"].append("toc-h2-first")

    return added


def sync(html: str, sub: bool = True) -> tuple[str, list[str], list[str], int]:
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
        if "toc-auto" in item.get("class", []):
            continue  # ข้าม sub-item ที่ generate เอง (sync เฉพาะบทจริง)
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

    sub_added = add_sub_toc(soup) if sub else 0

    return str(soup), updated, missing, sub_added


def main() -> int:
    parser = argparse.ArgumentParser(description="Sync TOC names + สารบัญย่อย h2 อัตโนมัติ")
    parser.add_argument("input", type=Path, help="Source HTML (e.g. book.html)")
    parser.add_argument(
        "-o", "--output", type=Path,
        help="Output path (default: <input>.synced.html)",
    )
    parser.add_argument(
        "--no-sub", action="store_true",
        help="ไม่สร้างสารบัญย่อย h2 (sync เฉพาะชื่อบทแบบเดิม)",
    )
    args = parser.parse_args()

    if not args.input.is_file():
        print(f"error: {args.input} not found", file=sys.stderr)
        return 1

    out_path = args.output or args.input.with_suffix(".synced.html")

    html = args.input.read_text(encoding="utf-8")
    new_html, updated, missing, sub_added = sync(html, sub=not args.no_sub)
    out_path.write_text(new_html, encoding="utf-8")

    print(f"wrote: {out_path}")
    print(f"updated {len(updated)} TOC entries")
    for cid in updated:
        print(f"  - #{cid}")

    if not args.no_sub:
        print(f"added {sub_added} sub-TOC (h2) entries")

    if missing:
        print(f"warn: {len(missing)} TOC entries have no matching chapter:", file=sys.stderr)
        for cid in missing:
            print(f"  - #{cid}", file=sys.stderr)

    return 0


if __name__ == "__main__":
    sys.exit(main())
