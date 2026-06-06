#!/usr/bin/env python3
"""
normalize_images.py

Pre-process HTML สำหรับ WeasyPrint: scale "กล่อง crop image" ให้พอดี text column
โดยใช้ uniform scale (ทั้ง width และ height คูณ k เดียวกัน) เพื่อรักษา aspect
→ overlay positions (.img-markers, .img-rect, .img-textbox, .img-lines) ยังตรง

ทำไมต้องสเกล:
- editor ของ image-annotator เซฟ <img> ด้วย width/height px ตายตัว + max-width:none
  เพื่อทับ CSS .book-img img { max-width: 62% } (ตั้งใจให้ครอป "เห็นกล่อง" ในเบราว์เซอร์)
- WeasyPrint แปลง px → pt ที่ 96dpi (1px = 0.75pt)
- 600px = 450pt อาจล้น text column ของหนังสือเล่มเล็ก (170mm → ~377pt)

วิธีแก้:
- หา <img> ที่มี object-fit ใน inline style + width/height px
- ถ้า width_pt > max_col_pt → คำนวณ k = max_col_pt / width_pt
- คูณ width + height ด้วย k (uniform) → aspect คงเดิม → overlay % ยังตรง
- เปลี่ยน unit จาก px → pt (ป้องกัน 96dpi quirk ในอนาคต)

Usage:
    python3 normalize_images.py input.html -o output.html --max-col-pt 377
"""

import argparse
import re
import sys
from pathlib import Path

from bs4 import BeautifulSoup


# 1px = 0.75pt ที่ 96dpi (WeasyPrint convention)
PX_TO_PT = 0.75

_WIDTH_PX_RE = re.compile(r"width\s*:\s*(\d+(?:\.\d+)?)\s*px", re.IGNORECASE)
_HEIGHT_PX_RE = re.compile(r"height\s*:\s*(\d+(?:\.\d+)?)\s*px", re.IGNORECASE)


def normalize(html: str, max_col_pt: float) -> tuple[str, list[dict]]:
    """สแกนทุก <img> — ถ้ามี object-fit + width/height px ที่เกิน max_col_pt → uniform scale

    Returns:
        (new_html, list of {alt, w_before_pt, h_before_pt, w_after_pt, h_after_pt, k})
    """
    soup = BeautifulSoup(html, "html.parser")
    actions: list[dict] = []

    for img in soup.find_all("img"):
        style = img.get("style") or ""
        if "object-fit" not in style.lower():
            continue  # ไม่ใช่ crop image — ปล่อย

        m_w = _WIDTH_PX_RE.search(style)
        m_h = _HEIGHT_PX_RE.search(style)
        if not (m_w and m_h):
            continue  # ไม่มี width/height px → อาจใช้ width auto หรือ pt อยู่แล้ว

        w_pt = float(m_w.group(1)) * PX_TO_PT
        h_pt = float(m_h.group(1)) * PX_TO_PT
        if w_pt <= max_col_pt:
            continue  # พอดี column อยู่แล้ว

        k = max_col_pt / w_pt
        new_w = w_pt * k        # = max_col_pt
        new_h = h_pt * k        # คูณ k เท่ากัน → aspect คงเดิม

        # เปลี่ยน px → pt ใน inline style (เก็บ key อื่นใน style ไว้เดิม)
        new_style = _WIDTH_PX_RE.sub(f"width:{new_w:.2f}pt", style)
        new_style = _HEIGHT_PX_RE.sub(f"height:{new_h:.2f}pt", new_style)
        img["style"] = new_style

        actions.append({
            "alt": img.get("alt", "(no alt)"),
            "w_before_pt": w_pt,
            "h_before_pt": h_pt,
            "w_after_pt": new_w,
            "h_after_pt": new_h,
            "k": k,
        })

    return str(soup), actions


def main() -> int:
    p = argparse.ArgumentParser(
        description="Scale crop-image <img> to fit text column (WeasyPrint pre-process)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument("input", type=Path, help="ไฟล์ HTML ต้นทาง")
    p.add_argument("-o", "--output", type=Path, help="ไฟล์ HTML ปลายทาง (default: <input>.norm.html)")
    p.add_argument(
        "--max-col-pt", type=float, required=True,
        help="ความกว้าง text column สูงสุด (pt) เช่น 377 สำหรับ 170mm book",
    )
    args = p.parse_args()

    if not args.input.is_file():
        print(f"✗ ไม่พบไฟล์: {args.input}", file=sys.stderr)
        return 1

    out_path = args.output or args.input.with_suffix(".norm.html")

    try:
        html_text = args.input.read_text(encoding="utf-8")
    except OSError as e:
        print(f"✗ อ่านไฟล์ไม่ได้: {e}", file=sys.stderr)
        return 1

    new_html, actions = normalize(html_text, args.max_col_pt)

    try:
        out_path.write_text(new_html, encoding="utf-8")
    except OSError as e:
        print(f"✗ เขียนไฟล์ไม่ได้: {e}", file=sys.stderr)
        return 1

    print(f"✓ normalize_images: ตรวจ {sum(1 for _ in BeautifulSoup(html_text, 'html.parser').find_all('img'))} <img>")
    print(f"  max-col: {args.max_col_pt:.1f}pt")
    print(f"  scale: {len(actions)} รูป (uniform — aspect คงเดิม)")
    for a in actions[:10]:  # แสดงสูงสุด 10 ตัวแรก
        print(
            f"    • {a['alt'][:40]:40} "
            f"{a['w_before_pt']:5.1f}×{a['h_before_pt']:5.1f}pt "
            f"→ {a['w_after_pt']:5.1f}×{a['h_after_pt']:5.1f}pt "
            f"(k={a['k']:.3f})"
        )
    if len(actions) > 10:
        print(f"    ... และอีก {len(actions) - 10} รูป")
    print(f"✓ บันทึก: {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
