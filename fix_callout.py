#!/usr/bin/env python3
"""
fix_callout.py
------------------------------------------------------------
Preprocessor: เติม inline fill="none" + stroke="transparent"
ลงใน <path class="img-line-hit"> ที่ขาดอยู่

ทำไม:
- WeasyPrint v68.x ไม่รองรับ `fill` กับ `stroke` เป็น CSS property
  → CSS เช่น `.img-line-hit { fill: none; }` ถูก ignore
  → SVG default fill = "black" → เส้นโค้ง/มุมระบายดำ
- Editor บางรุ่นยังไม่ใส่ inline attribute ให้
  → ใช้ script นี้ patch HTML ก่อนส่งให้ WeasyPrint

idempotent:
- ถ้า path มี fill="..." อยู่แล้ว → ไม่แตะ
- ถ้า path มี stroke="..." อยู่แล้ว → ไม่แตะ
- รันซ้ำได้ ไม่ทำให้เพี้ยน

usage:
    python3 fix_callout.py input.html -o output.html
    python3 fix_callout.py input.html  # overwrite in place
"""

import argparse
import re
import sys
from pathlib import Path


# match: <path ... class="...img-line-hit..." ... />  หรือ </path>
# group 1 = ทั้ง attributes ก่อน close tag
# group 2 = close tag (/> หรือ >)
_PATH_HIT_RE = re.compile(
    r'(<path\s+[^>]*?class="[^"]*\bimg-line-hit\b[^"]*"[^>]*?)(\s*/?>)',
    re.IGNORECASE,
)

_HAS_FILL_RE   = re.compile(r'\bfill\s*=\s*["\']', re.IGNORECASE)
_HAS_STROKE_RE = re.compile(r'\bstroke\s*=\s*["\']', re.IGNORECASE)


def patch_hit_zones(html: str) -> tuple[str, int]:
    """
    เติม fill="none" + stroke="transparent" ลง <path class="img-line-hit"> ที่ขาด
    return: (new_html, num_patched)
    """
    patched = 0

    def _patch(m: re.Match) -> str:
        nonlocal patched
        attrs = m.group(1)
        close = m.group(2)
        added = []
        if not _HAS_FILL_RE.search(attrs):
            added.append('fill="none"')
        if not _HAS_STROKE_RE.search(attrs):
            added.append('stroke="transparent"')
        if added:
            patched += 1
            return f'{attrs} {" ".join(added)}{close}'
        return m.group(0)

    new_html = _PATH_HIT_RE.sub(_patch, html)
    return new_html, patched


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Patch <path class='img-line-hit'> to add fill='none' "
                    "stroke='transparent' (WeasyPrint compat fix)"
    )
    ap.add_argument("input", help="input HTML file")
    ap.add_argument("-o", "--output", help="output HTML file (default: overwrite input)")
    args = ap.parse_args()

    in_path = Path(args.input)
    out_path = Path(args.output) if args.output else in_path

    if not in_path.is_file():
        print(f"ERROR: input file not found: {in_path}", file=sys.stderr)
        return 1

    html = in_path.read_text(encoding="utf-8")
    new_html, n = patch_hit_zones(html)

    out_path.write_text(new_html, encoding="utf-8")
    if n > 0:
        print(f"✓ Patched {n} <path class='img-line-hit'> element(s) "
              f"→ {out_path}")
    else:
        print(f"✓ No patches needed (editor already adds inline attributes) "
              f"→ {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
