#!/usr/bin/env python3
"""
fix_gradient.py
------------------------------------------------------------
Preprocessor: แทน CSS gradient ใน inline style ของ HTML ด้วย "สีพื้น" (solid)

ทำไม:
- mutool recolor 1.27.2 *segfault* (exit -11 / SIGSEGV) เมื่อ PDF มี gradient
  (linear / radial / conic) — crash ทั้ง gray และ cmyk
- gradient ที่มาจาก inline style="..." ใน HTML ไม่ผูกกับ @media
  → แก้ media="screen" ก็คุมไม่ถึง → ต้อง patch ที่ HTML ก่อนส่ง WeasyPrint
- editor (เช่นกล่อง .note / .note-label) ฝัง linear-gradient มาเป็น inline เสมอ

หลักการแทน (ทำระดับ "declaration" เพื่อให้ได้ CSS ที่ valid):
- `background: linear-gradient(...) <color>`  → `background: <color>`
      (เก็บสีพื้นที่ติดมาใน shorthand ไว้ — มักเป็น fallback ที่ตั้งใจ)
- `background: linear-gradient(...)`           → `background: <stop แรก>`
- `background-image: linear-gradient(...)`     → `background-image: none;
                                                  background-color: <stop แรก>`
      (ถ้ายังไม่มี background-color ใน style เดิม)
→ WeasyPrint จะ render เป็นสีพื้น ไม่มี gradient ใน PDF → mutool ไม่ crash
→ เก็บโทนสีเดิมไว้ (ใช้ "สี stop แรก" ของ gradient เช่น note-label ยังฟ้า)

idempotent:
- style ที่ไม่มีคำว่า gradient → ไม่แตะ
- รันซ้ำได้ ผลไม่เปลี่ยน (รอบสองไม่มี gradient เหลือแล้ว)

usage:
    python3 fix_gradient.py input.html -o output.html
    python3 fix_gradient.py input.html            # overwrite in place
"""

import argparse
import re
import sys
from pathlib import Path


# ฟังก์ชัน gradient ที่ต้องจัดการ (รวม repeating-*)
_GRAD_FUNCS = (
    "repeating-linear-gradient", "repeating-radial-gradient",
    "linear-gradient", "radial-gradient", "conic-gradient",
)

# inline style attribute — value ไม่มี " ข้างใน (ใช้เป็น delimiter)
_STYLE_ATTR_RE = re.compile(r'style\s*=\s*"([^"]*)"', re.IGNORECASE)

# color tokens
_COLOR_FUNC_RE = re.compile(r'^(rgba?|hsla?)\s*\(', re.IGNORECASE)
_HEX_RE = re.compile(r'^#[0-9a-fA-F]{3,8}\b')
# angle / direction → ไม่ใช่สี (ต้อง skip ก่อนหา stop แรก)
_DIRECTION_RE = re.compile(
    r'(^to\s)|(\b\d*\.?\d+(deg|grad|rad|turn)\b)|(\bfrom\s)|(\bat\s)',
    re.IGNORECASE,
)


def _split_top_commas(s: str) -> list[str]:
    """split ด้วย comma ที่อยู่ "นอกวงเล็บ" เท่านั้น (กัน rgb(...) ข้างในพัง)"""
    parts, depth, cur = [], 0, []
    for ch in s:
        if ch == "(":
            depth += 1
            cur.append(ch)
        elif ch == ")":
            depth -= 1
            cur.append(ch)
        elif ch == "," and depth == 0:
            parts.append("".join(cur))
            cur = []
        else:
            cur.append(ch)
    parts.append("".join(cur))
    return parts


def _extract_color(seg: str) -> str | None:
    """ดึง color token ตัวแรกจาก segment เช่น 'rgb(66,133,244) 0%' → 'rgb(66,133,244)'"""
    seg = seg.strip()
    if not seg:
        return None
    if seg.startswith("#"):
        m = _HEX_RE.match(seg)
        return m.group(0) if m else None
    if _COLOR_FUNC_RE.match(seg):
        # จับจนถึง ')' ที่ปิดสมดุล
        depth = 0
        for i, ch in enumerate(seg):
            if ch == "(":
                depth += 1
            elif ch == ")":
                depth -= 1
                if depth == 0:
                    return seg[: i + 1]
        return None
    # named color (เช่น red, white) — เอาคำแรก
    return seg.split()[0]


def _find_gradient_span(value: str) -> tuple[int, int, str] | None:
    """หา gradient(...) ตัวแรกใน value → (start, end_exclusive, inner) แบบ balanced parens"""
    low = value.lower()
    best = None
    for fn in _GRAD_FUNCS:
        idx = low.find(fn + "(")
        if idx != -1 and (best is None or idx < best[0]):
            best = (idx, fn)
    if best is None:
        return None
    start, fn = best
    open_paren = start + len(fn)
    depth = 0
    for i in range(open_paren, len(value)):
        if value[i] == "(":
            depth += 1
        elif value[i] == ")":
            depth -= 1
            if depth == 0:
                inner = value[open_paren + 1 : i]
                return (start, i + 1, inner)
    return None  # ไม่ปิดวงเล็บ (malformed) → ปล่อยไว้


def _first_stop_color(inner: str) -> str | None:
    """หา 'สี stop แรก' ของ gradient (ข้าม angle/direction ก่อน)"""
    segs = _split_top_commas(inner)
    if not segs:
        return None
    first = segs[0].strip()
    # ถ้า segment แรกเป็น angle/direction → stop แรกอยู่ segment ถัดไป
    if _DIRECTION_RE.search(first) and not first.startswith("#") \
            and not _COLOR_FUNC_RE.match(first):
        seg = segs[1].strip() if len(segs) > 1 else first
    else:
        seg = first
    return _extract_color(seg)


def _solid_outside_gradient(value: str, gstart: int, gend: int) -> str | None:
    """หา color token ที่อยู่ "นอก" gradient ใน shorthand (เช่น background: grad() #fff)"""
    rest = (value[:gstart] + " " + value[gend:]).strip()
    if not rest:
        return None
    # หา color token แรกใน rest (hex / rgb() / hsl())
    m = re.search(r"#[0-9a-fA-F]{3,8}\b", rest)
    if m:
        return m.group(0)
    m = re.search(r"(rgba?|hsla?)\s*\([^)]*\)", rest, re.IGNORECASE)
    if m:
        return m.group(0)
    return None


def _transform_style(style: str) -> tuple[str, int]:
    """แปลง 1 ค่า inline style → (style ใหม่, จำนวน gradient ที่แทน)"""
    if "gradient" not in style.lower():
        return style, 0

    decls = style.split(";")
    has_bg_color = any(
        ":" in d and d.split(":", 1)[0].strip().lower() == "background-color"
        for d in decls
    )
    out: list[str] = []
    extra: list[str] = []
    changed = 0

    for d in decls:
        if ":" not in d:
            out.append(d)
            continue
        prop, val = d.split(":", 1)
        p = prop.strip().lower()
        if "gradient" not in val.lower() or p not in ("background", "background-image"):
            out.append(d)
            continue

        span = _find_gradient_span(val)
        if span is None:
            out.append(d)
            continue
        gstart, gend, inner = span
        solid = _first_stop_color(inner)
        if solid is None:
            out.append(d)
            continue

        if p == "background":
            # เก็บสีพื้นที่ติดมาใน shorthand ก่อน (fallback ที่ตั้งใจ) ไม่งั้นใช้ stop แรก
            color = _solid_outside_gradient(val, gstart, gend) or solid
            indent = prop[: len(prop) - len(prop.lstrip())]
            out.append(f"{indent}background: {color}")
        else:  # background-image
            indent = prop[: len(prop) - len(prop.lstrip())]
            out.append(f"{indent}background-image: none")
            if not has_bg_color:
                extra.append(f"background-color: {solid}")
                has_bg_color = True
        changed += 1

    result = ";".join(out)
    if extra:
        result = result.rstrip(";").rstrip() + "; " + "; ".join(extra)
    return result, changed


def patch_gradients(html: str) -> tuple[str, int]:
    """แทน gradient ในทุก inline style → return (html ใหม่, จำนวน gradient ที่แทน)"""
    total = 0

    def _sub(m: re.Match) -> str:
        nonlocal total
        new_style, n = _transform_style(m.group(1))
        total += n
        if n == 0:
            return m.group(0)
        return f'style="{new_style}"'

    new_html = _STYLE_ATTR_RE.sub(_sub, html)
    return new_html, total


def main() -> int:
    ap = argparse.ArgumentParser(
        description="แทน CSS gradient ใน inline style ด้วยสีพื้น "
                    "(กัน mutool recolor segfault)"
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
    new_html, n = patch_gradients(html)

    out_path.write_text(new_html, encoding="utf-8")
    if n > 0:
        print(f"✓ แทน gradient → สีพื้น {n} จุด (กัน mutool segfault) → {out_path}")
    else:
        print(f"✓ ไม่พบ inline gradient (ปลอดภัยอยู่แล้ว) → {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
