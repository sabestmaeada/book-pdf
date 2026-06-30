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
# ความกว้าง canvas ของ editor (px) — อนุมานจากรูป annotation ที่ใช้ width:700px = เต็ม canvas
# ใช้สเกล height:px ของรูป crop (non-frame) ให้ box aspect ตรง editor ตอน column แคบลง
EDITOR_COL_PX = 700

_WIDTH_PX_RE = re.compile(r"width\s*:\s*(\d+(?:\.\d+)?)\s*px", re.IGNORECASE)
_HEIGHT_PX_RE = re.compile(r"height\s*:\s*(\d+(?:\.\d+)?)\s*px", re.IGNORECASE)
# width เป็น % (ไม่จับ max-width) — ใช้แปลงรูปใน .img-frame เป็น pt สัมบูรณ์
_WIDTH_PCT_RE = re.compile(r"(?<!-)\bwidth\s*:\s*(\d+(?:\.\d+)?)\s*%", re.IGNORECASE)
# height หน่วยใดก็ได้ (px/pt/%) — ใช้แทนค่าตอนปรับ aspect
_HEIGHT_ANY_RE = re.compile(r"(?<!-)\bheight\s*:\s*\d+(?:\.\d+)?\s*(?:px|pt|%)", re.IGNORECASE)
# มี inline height ไหม (ไม่จับ max-height / line-height — (?<!-) กัน "-height")
# ใช้แยก annotation 2 แบบ: มี height = "marker บนรูป" / ไม่มี = "callout ข้างรูป"
_HAS_HEIGHT_RE = re.compile(r"(?<!-)\bheight\s*:", re.IGNORECASE)


def _line_aspect(frame) -> float | None:
    """อ่าน aspect (h/w) ของ svg.img-lines ใน frame → ใช้ปรับ height ให้กล่องรูปตรง viewBox
    (preserveAspectRatio="none" สเกล x/y ตาม viewBox — ถ้า box aspect ไม่ตรง วงกลมปลายเส้นจะรี)"""
    svg = frame.find("svg", class_="img-lines")
    if svg is None:
        return None
    vb = svg.get("viewbox") or svg.get("viewBox")
    if vb:
        parts = vb.replace(",", " ").split()
        if len(parts) == 4:
            try:
                w, h = float(parts[2]), float(parts[3])
                if w > 0:
                    return h / w
            except ValueError:
                pass
    dh = svg.get("data-h")
    if dh:
        try:
            return float(dh) / 100.0
        except ValueError:
            pass
    return None


def normalize(html: str, max_col_pt: float) -> tuple[str, list[dict]]:
    """สแกนทุก <img> — ถ้ามี object-fit + width/height px ที่เกิน max_col_pt → uniform scale

    Returns:
        (new_html, list of {alt, w_before_pt, h_before_pt, w_after_pt, h_after_pt, k})
    """
    soup = BeautifulSoup(html, "html.parser")
    actions: list[dict] = []
    frame_actions: list[dict] = []

    for img in soup.find_all("img"):
        style = img.get("style") or ""

        # รูปใน .img-frame (annotation) — แยก 2 รูปแบบด้วย "มี inline height ไหม"
        # เพราะ overlay (เส้น/marker/textbox) อ้างอิงขนาด frame → frame ต้องถูกต้อง
        frame = img.find_parent(class_="img-frame")
        if frame is not None:
            ar = _line_aspect(frame)   # aspect (h/w) จาก viewBox ของ svg เส้นชี้

            if _HAS_HEIGHT_RE.search(style):
                # ── Pattern B "marker บนรูป" (เช่น width:700px height:360px object-fit) ──
                #   รูปใหญ่เต็ม frame, overlay อยู่บนรูป → frame หดเท่ารูป (inline-block)
                #   width (% หรือ px) → pt cap ที่ column; height = width×ar
                #   → box aspect = viewBox aspect → svg สเกล x/y เท่ากัน → cap กลม
                w = None
                m_pct = _WIDTH_PCT_RE.search(style)
                m_px = _WIDTH_PX_RE.search(style)
                if m_pct:
                    w = min(float(m_pct.group(1)) / 100.0 * max_col_pt, max_col_pt)
                    style = _WIDTH_PCT_RE.sub(f"width:{w:.2f}pt", style)
                elif m_px:
                    w = min(float(m_px.group(1)) * PX_TO_PT, max_col_pt)
                    style = _WIDTH_PX_RE.sub(f"width:{w:.2f}pt", style)
                if w is not None:
                    if ar:
                        style = _HEIGHT_ANY_RE.sub(f"height:{w * ar:.2f}pt", style)
                    img["style"] = style
                    frame_actions.append({"alt": img.get("alt", "(no alt)"), "mode": "on-image", "w_pt": w})

            elif _WIDTH_PCT_RE.search(style):
                # ── Pattern A "callout ข้างรูป" (% width, ไม่มี height) ──
                #   รูปเล็ก (เช่น 30%) + กล่อง/เส้นอยู่ "ข้าง" รูป → frame ต้องกว้างเท่า column
                m_pct = _WIDTH_PCT_RE.search(style)
                if ar:
                    #   frame = canvas: column กว้าง × (column×ar) สูง, รูปกึ่งกลาง (flex)
                    #   image width คง % ไว้ (% ของ frame width ชัดเจน → ไม่ circular)
                    fw, fh = max_col_pt, max_col_pt * ar
                    fstyle = (frame.get("style") or "").rstrip("; ").strip()
                    frame["style"] = (f"{fstyle};" if fstyle else "") + f"width:{fw:.2f}pt;height:{fh:.2f}pt"
                    cls = frame.get("class", []) or []
                    if "img-frame-canvas" not in cls:
                        cls.append("img-frame-canvas")
                        frame["class"] = cls
                    frame_actions.append({"alt": img.get("alt", "(no alt)"), "mode": "canvas", "w_pt": fw, "h_pt": fh})
                else:
                    #   ไม่มีเส้นชี้ (ar=None) → กัน inline-block ยุบ: แค่ width %→pt
                    w = min(float(m_pct.group(1)), 100.0) / 100.0 * max_col_pt
                    img["style"] = _WIDTH_PCT_RE.sub(f"width:{w:.2f}pt", style)
                    frame_actions.append({"alt": img.get("alt", "(no alt)"), "mode": "no-lines", "w_pt": w})

            # else: plain (ไม่มี width) → คง inline-block, รูปเต็ม column ตามธรรมชาติ
            #   frame = รูป (col × ส่วนสูงจริง) → overlay อยู่บนรูป, ไม่ต้อง canvas

            continue   # รูปใน frame จบที่นี่ — ไม่เข้า px-overflow block ด้านล่าง

        if "object-fit" not in style.lower():
            continue  # ไม่ใช่ crop image — ปล่อย

        # รูป crop "ไม่มี frame": แปลงขนาดให้ตรง editor
        #   หลักการ: px ทุกค่าสัมพัทธ์กับ editor column (700px) → print = (px/700)×max_col
        #            width:% คงไว้ (สัมพัทธ์อยู่แล้ว) ; px → สเกล uniform editor→print
        #   เหตุที่ต้องสเกล:
        #     - width:px เกิน column: เดิม scale-to-fit เป็น "เต็ม column" (ผิด — editor ไม่เต็ม
        #       เช่น 600px = 86% ของ editor 700px แต่ออกมาเต็ม 100%)
        #     - width:% + height:px: width หดตาม column แต่ height:px คงที่ → box aspect เพี้ยน
        #       → object-fit:cover ตัด crop ต่างจาก editor
        #   สเกลทุก px ด้วยอัตราเดียว (editor→print) → ขนาด + box aspect ตรง editor
        #   ⚠ annotation จัดการที่ frame block ด้านบนแล้ว (continue ก่อน) — ตรงนี้เฉพาะรูปไม่มี frame
        m_wpx = _WIDTH_PX_RE.search(style)
        m_hpx = _HEIGHT_PX_RE.search(style)
        if not (m_wpx or m_hpx):
            continue  # ไม่มี px → width auto/%/pt อยู่แล้ว ไม่ต้องแปลง

        scale = max_col_pt / EDITOR_COL_PX
        if m_wpx:
            scale = min(scale, max_col_pt / float(m_wpx.group(1)))  # cap: width ไม่ล้น column
        new_w = new_h = None
        if m_wpx:
            new_w = float(m_wpx.group(1)) * scale
            style = _WIDTH_PX_RE.sub(f"width:{new_w:.2f}pt", style)
        if m_hpx:
            new_h = float(m_hpx.group(1)) * scale
            style = _HEIGHT_PX_RE.sub(f"height:{new_h:.2f}pt", style)
        img["style"] = style

        actions.append({
            "alt": img.get("alt", "(no alt)"),
            "w_before_pt": (float(m_wpx.group(1)) * PX_TO_PT) if m_wpx else 0.0,
            "h_before_pt": (float(m_hpx.group(1)) * PX_TO_PT) if m_hpx else 0.0,
            "w_after_pt": new_w or 0.0,
            "h_after_pt": new_h or 0.0,
            "k": scale / PX_TO_PT,
        })

    return str(soup), actions, frame_actions


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

    new_html, actions, frame_actions = normalize(html_text, args.max_col_pt)

    try:
        out_path.write_text(new_html, encoding="utf-8")
    except OSError as e:
        print(f"✗ เขียนไฟล์ไม่ได้: {e}", file=sys.stderr)
        return 1

    print(f"✓ normalize_images: ตรวจ {sum(1 for _ in BeautifulSoup(html_text, 'html.parser').find_all('img'))} <img>")
    print(f"  max-col: {args.max_col_pt:.1f}pt")
    print(f"  annotation (รูปใน .img-frame): {len(frame_actions)} รูป")
    for a in frame_actions[:10]:
        print(f"    • {a['alt'][:40]:40} [{a['mode']}] w={a['w_pt']:.1f}pt"
              + (f" h={a['h_pt']:.1f}pt" if a.get("h_pt") else ""))
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
