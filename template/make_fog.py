#!/usr/bin/env python3
"""
make_fog.py — สร้างภาพ "หมอกฟุ้ง" (soft radial fog) เป็น PNG + พิมพ์ base64 data URI

ทำไมต้อง raster:
- CSS gradient (linear/radial) ทำ mutool recolor 1.27.2 segfault (crash)
  → fog ต้องเป็น "ภาพ" ไม่ใช่ vector → ผ่าน mutool ได้ปกติ
- PNG fog หน้าตาเหมือน gradient ทุกประการ (เนียนกว่าด้วย เพราะ blur จริง)

ปรับ theme:
- แก้ค่าใน CONFIG ด้านล่าง (สี / blob / ความเข้ม) แล้วรันใหม่
- เอา base64 ที่พิมพ์ออกมา ไปแทนใน custom-print.css (.ch-hdr background-image)

Usage:
    python3 template/make_fog.py                 # พิมพ์ base64 + เซฟ fog_preview.png
    python3 template/make_fog.py -o fog.png       # เซฟไฟล์ PNG ด้วย
"""

import argparse
import base64
import io
import math
import sys

from PIL import Image, ImageFilter


# ============================================================
# CONFIG — ปรับ theme ที่นี่
# ============================================================
# สี fog (RGB) — ค่า default ส้มจากธีม sparkle
FOG_RGB = (216, 102, 53)        # #D86635

# ขนาดภาพ (px) — fog เนียน ใช้ res ไม่สูงก็พอ (background-size จะ scale ให้)
W, H = 560, 150

# blobs: (cx%, cy%, radius% ของ W, peak_alpha 0..1)
#   จัดให้ fog อยู่หลัง: ก้อนซ้าย (เลขบท) / กลาง (ชื่อบท)
#   ตัดก้อนขวาออก + fade ขวาแรง → fog ไม่ถึงดาวใหญ่
BLOBS = [
    (0.16, 0.52, 0.26, 0.11),   # ซ้าย — เข้มสุด (หลัง "01")
    (0.45, 0.50, 0.22, 0.06),   # กลาง — หลังชื่อบท
]

# blur เพิ่มความฟุ้ง (px) — สูง = ฟุ้งมาก
BLUR = 16

# edge fade — fog จางเป็น 0 ก่อนถึงขอบ (apply หลัง blur → ขอบสะอาดเสมอ)
#   ค่า = สัดส่วนความกว้าง/สูงที่ใช้ ramp จากขอบเข้ามา (0 = ปิด)
#   ⚠ MARGIN_R สูง = fade ขวาเร็ว → fog ไม่ถึงดาวใหญ่ขวา
#   ⚠ MARGIN_Y สูง = หมอกหดเข้ากลางแนวตั้ง (ขอบบน-ล่างหายสนิท)
MARGIN_L = 0.20   # ขอบซ้าย
MARGIN_R = 0.42   # ขอบขวา (แรงกว่า — กัน fog ชนดาวใหญ่)
MARGIN_Y = 0.42   # ขอบบน-ล่าง

# preset "part" — fog ก้อนกลางสำหรับหน้า part divider (เต็มหน้า center)
#   ภาพเกือบจตุรัส + blob กลาง 1 ก้อน + fade รอบด้านสมมาตร → glow นุ่มหลังข้อความ
PART_PRESET = {
    "W": 440, "H": 300,
    "BLOBS": [(0.50, 0.50, 0.40, 0.10)],
    "BLUR": 22,
    "MARGIN_L": 0.26, "MARGIN_R": 0.26, "MARGIN_Y": 0.26,
}
# ============================================================


def _smoothstep(edge0: float, edge1: float, x: float) -> float:
    if edge1 <= edge0:
        return 1.0 if x >= edge1 else 0.0
    t = (x - edge0) / (edge1 - edge0)
    t = max(0.0, min(1.0, t))
    return t * t * (3.0 - 2.0 * t)


def _edge_factor(x: int, y: int) -> float:
    """1.0 กลางภาพ → 0.0 ที่ขอบ (ramp แยกซ้าย/ขวา/บน-ล่าง)"""
    fx = x / W
    fy = y / H
    wl = _smoothstep(0, MARGIN_L, fx)        # ขอบซ้าย
    wr = _smoothstep(0, MARGIN_R, 1 - fx)    # ขอบขวา (margin ต่างได้)
    wy = _smoothstep(0, MARGIN_Y, fy) * _smoothstep(0, MARGIN_Y, 1 - fy)
    return wl * wr * wy


def make_fog() -> Image.Image:
    """สร้างภาพ fog RGBA โปร่งใส"""
    # alpha map (float) — สะสมจากทุก blob ด้วย Gaussian falloff
    alpha = [[0.0] * W for _ in range(H)]
    for cx_f, cy_f, r_f, peak in BLOBS:
        cx, cy = cx_f * W, cy_f * H
        sigma = r_f * W
        two_sigma2 = 2.0 * sigma * sigma
        for y in range(H):
            dy2 = (y - cy) ** 2
            row = alpha[y]
            for x in range(W):
                d2 = (x - cx) ** 2 + dy2
                a = peak * math.exp(-d2 / two_sigma2)
                if a > row[x]:
                    row[x] = a   # ใช้ max (ไม่บวกซ้อน — กัน hotspot เข้มเกิน)

    img = Image.new("RGBA", (W, H), (FOG_RGB[0], FOG_RGB[1], FOG_RGB[2], 0))
    px = img.load()
    for y in range(H):
        for x in range(W):
            a = min(1.0, alpha[y][x])
            px[x, y] = (FOG_RGB[0], FOG_RGB[1], FOG_RGB[2], int(round(a * 255)))

    # blur ก่อน → แล้วค่อย apply edge-fade
    # (ถ้า fade ก่อน blur จะดันหมอกกลับมาขอบ → ขอบไม่สะอาด)
    if BLUR > 0:
        img = img.filter(ImageFilter.GaussianBlur(BLUR))

    # edge-fade หลัง blur → ขอบโปร่งใสสนิทเสมอ
    px = img.load()
    for y in range(H):
        for x in range(W):
            r, g, b, a = px[x, y]
            px[x, y] = (r, g, b, int(round(a * _edge_factor(x, y))))
    return img


def to_data_uri(img: Image.Image) -> str:
    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    b64 = base64.b64encode(buf.getvalue()).decode("ascii")
    return f"data:image/png;base64,{b64}", len(buf.getvalue())


def main() -> int:
    ap = argparse.ArgumentParser(description="Generate soft fog PNG + base64 data URI")
    ap.add_argument("-o", "--output", help="เซฟ PNG ไปไฟล์นี้ด้วย (optional)")
    ap.add_argument("--preset", choices=["header", "part"], default="header",
                    help="header = fog หัวบท (default) / part = fog หน้า part (ก้อนกลาง)")
    args = ap.parse_args()

    if args.preset == "part":
        globals().update(PART_PRESET)   # override W/H/BLOBS/BLUR/MARGIN_* ก่อน generate

    img = make_fog()
    if args.output:
        img.save(args.output)
        print(f"✓ เซฟ PNG: {args.output} ({img.width}×{img.height})", file=sys.stderr)

    uri, nbytes = to_data_uri(img)
    print(f"✓ fog PNG: {img.width}×{img.height}px, {nbytes/1024:.1f}KB, "
          f"base64 {len(uri)/1024:.1f}KB", file=sys.stderr)
    print(f"  สี #{FOG_RGB[0]:02X}{FOG_RGB[1]:02X}{FOG_RGB[2]:02X}, "
          f"{len(BLOBS)} blobs, blur {BLUR}px", file=sys.stderr)
    print()
    print(uri)   # stdout = data URI อย่างเดียว → pipe/copy ง่าย
    return 0


if __name__ == "__main__":
    sys.exit(main())
