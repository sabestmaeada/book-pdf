"""
Flask local UI for the book PDF pipeline.

Run with:
    cd ui && python3 app.py
or via the launcher:
    ./start_ui.sh
"""

import io
import json
import re
import shutil
import subprocess
import threading
import time
import zipfile
from pathlib import Path
from queue import Queue, Empty

import pikepdf
from flask import Flask, Response, abort, jsonify, render_template, request, send_file


# ---------- Regex สำหรับหา CMYK / RGB color operators ใน content stream ----------
# CMYK: "<c> <m> <y> <k> k" (fill) หรือ "K" (stroke)
_CMYK_OP_RE = re.compile(
    rb'(?<![\d.])(\d*\.?\d+)\s+(\d*\.?\d+)\s+(\d*\.?\d+)\s+(\d*\.?\d+)\s+([kK])(?=\s|$)'
)
# RGB: "<r> <g> <b> rg" (fill) หรือ "RG" (stroke)
_RGB_OP_RE = re.compile(
    rb'(?<![\d.])(\d*\.?\d+)\s+(\d*\.?\d+)\s+(\d*\.?\d+)\s+(rg|RG)(?=\s|$)'
)


def _format_k(v: float) -> bytes:
    """format K value as compact bytes — 0, 1, หรือ 0.xxx"""
    if v >= 0.999: return b'1'
    if v <= 0.001: return b'0'
    s = f'{v:.3f}'.rstrip('0').rstrip('.')
    return s.encode() if s else b'0'


def _force_k100_in_stream(data: bytes) -> tuple[bytes, int]:
    """แทน CMYK/RGB color operators ที่เป็น "near-neutral" → K-only equivalent
       เกณฑ์ neutral: CMY (หรือ RGB) ใกล้เคียงกัน (max - min < threshold)
       เช่น CMYK(0.63, 0.56, 0.56, 0) → K0.58 หรือ RGB(0.5, 0.5, 0.5) → K0.5
       ถ้า K_new > 0.95 → snap เป็น K100
       คืน (new_bytes, replacement_count)
    """
    count = 0

    def cmyk_sub(m):
        nonlocal count
        c, mm, y, k = float(m.group(1)), float(m.group(2)), float(m.group(3)), float(m.group(4))
        op = m.group(5)
        cmy_max = max(c, mm, y)
        cmy_min = min(c, mm, y)
        # ไม่ neutral → เป็นสีจริง ไม่แตะ
        if cmy_max - cmy_min >= 0.15:
            return m.group(0)
        # white-ish: ทุก channel ใกล้ 0 → ไม่ต้องแตะ
        if k < 0.01 and cmy_max < 0.01:
            return m.group(0)
        # K100 อยู่แล้ว (K=1, CMY=0) → ไม่ต้องแตะ
        if k > 0.99 and cmy_max < 0.05:
            return m.group(0)
        # คำนวณ K-only equivalent (subtractive blend approx)
        cmy_avg = (c + mm + y) / 3
        k_new = min(1.0, k + (1.0 - k) * cmy_avg)
        if k_new > 0.95:
            k_new = 1.0
        count += 1
        return b'0 0 0 ' + _format_k(k_new) + b' ' + op

    def rgb_sub(m):
        nonlocal count
        r, g, b = float(m.group(1)), float(m.group(2)), float(m.group(3))
        op = m.group(4)
        rgb_max = max(r, g, b)
        rgb_min = min(r, g, b)
        # ไม่ neutral → สีจริง ไม่แตะ
        if rgb_max - rgb_min >= 0.05:
            return m.group(0)
        # invert: RGB 1=white → K=0, RGB 0=black → K=1
        rgb_avg = (r + g + b) / 3
        k_new = 1.0 - rgb_avg
        # white → ไม่ต้องแตะ (ทำให้มี 0 0 0 0 k ก็ไม่มีประโยชน์)
        if k_new < 0.01:
            return m.group(0)
        if k_new > 0.95:
            k_new = 1.0
        count += 1
        new_op = b'k' if op == b'rg' else b'K'
        return b'0 0 0 ' + _format_k(k_new) + b' ' + new_op

    data = _CMYK_OP_RE.sub(cmyk_sub, data)
    data = _RGB_OP_RE.sub(rgb_sub, data)
    return data, count


def enforce_k100_text(pdf_path: Path, q: Queue) -> None:
    """Post-process PDF: บังคับ text/vector ดำใน content streams เป็น K100"""
    total = 0
    pages_modified = 0
    with pikepdf.open(pdf_path, allow_overwriting_input=True) as pdf:
        for page in pdf.pages:
            contents = page.get('/Contents')
            if contents is None:
                continue
            streams = list(contents) if isinstance(contents, pikepdf.Array) else [contents]
            page_count = 0
            for stream in streams:
                try:
                    data = stream.read_bytes()
                except Exception:
                    continue
                new_data, n = _force_k100_in_stream(data)
                if n > 0:
                    stream.write(new_data)
                    page_count += n
            if page_count:
                total += page_count
                pages_modified += 1
        pdf.save(pdf_path)
    q.put(f"  K100 enforce: replaced {total} near-black color ops ใน {pages_modified} pages")

ROOT = Path(__file__).parent.parent.resolve()
INPUT_DIR = ROOT / "input"
OUTPUT_DIR = ROOT / "output"
ASSETS_DIR = ROOT / "assets"
CSS_DIR = ROOT / "css"
SIZES_DIR = CSS_DIR / "sizes"
STYLES_DIR = CSS_DIR / "styles"
PROFILES_DIR = ROOT / "profiles"
SYNC_SCRIPT = ROOT / "sync_toc.py"
NORMALIZE_SCRIPT = ROOT / "normalize_images.py"
FIX_CALLOUT_SCRIPT = ROOT / "fix_callout.py"
FIX_GRADIENT_SCRIPT = ROOT / "fix_gradient.py"

# ค่ามาตรฐานสำหรับพิมพ์ — โหลดเมื่อ user ไม่ upload Template CSS ส่วนตัว
DEFAULT_PRINT_CSS = ROOT / "template" / "_default_print.css"

# margin constants (mm) — match @page rule ใน size_*.css
# text column width = trim_width − INNER_GUTTER − OUTER_MARGIN
INNER_GUTTER_MM = 22
OUTER_MARGIN_MM = 15
SAFETY_PT = 5            # เผื่อ rounding/edge cases
MM_TO_PT = 2.8346

_SIZE_FILE_RE = re.compile(r"size_(\d+)x(\d+)\.css$", re.IGNORECASE)


def compute_text_column_pt(size_css: str) -> float:
    """คำนวณความกว้าง text column สูงสุดจากชื่อไฟล์ size CSS
       เช่น 'sizes/size_170x228.css' → 170mm − 22mm − 15mm = 133mm = 377pt − 5pt safety = 372pt
    """
    m = _SIZE_FILE_RE.search(size_css)
    if not m:
        return 360.0  # fallback กลางๆ
    book_w_mm = int(m.group(1))
    col_mm = book_w_mm - INNER_GUTTER_MM - OUTER_MARGIN_MM
    return col_mm * MM_TO_PT - SAFETY_PT

# Auto-detect ขนาด + สไตล์ จากชื่อไฟล์ใน subfolder
# Path layout:
#   css/sizes/size_<W>x<H>.css             — กำหนดขนาดหน้า + bleed (geometry)
#   css/styles/style_<variant>[_<sub>].css — กำหนด typography + colors + layout
_SIZE_PATTERN = re.compile(r"^size_(\d+)x(\d+)\.css$", re.IGNORECASE)
_STYLE_PATTERN = re.compile(r"^style_([a-z][a-z0-9]*)(?:_([a-z0-9_]+))?\.css$", re.IGNORECASE)

# Pattern สำหรับ "หน้าที่ต้องการ" — รองรับ 1 หรือ 4-20 หรือ 1,4-8,12 (มีเว้นวรรคได้)
_PAGES_PATTERN = re.compile(r"^\s*\d+(?:\s*-\s*\d+)?(?:\s*,\s*\d+(?:\s*-\s*\d+)?)*\s*$")

# Style variant → ICC color space signatures ที่เข้ากันได้
# (signature ขนาด 4 ตัวอักษร ตาม ICC.1:2010 — RGB มี space ต่อท้าย)
_STYLE_ICC_MAP = {
    "bw":    ["GRAY"],
    "gray":  ["GRAY"],
    "mono":  ["GRAY"],
    "cmyk":  ["CMYK"],
    "rgb":   ["RGB "],
    "color": ["RGB "],
}

# Style variant → label ที่แสดงใน dropdown
_STYLE_LABELS = {
    "bw":    "ขาวดำ (B&W)",
    "gray":  "ขาวดำ (Grayscale)",
    "mono":  "ขาวดำ (Mono)",
    "cmyk":  "CMYK (สี่สี)",
    "rgb":   "สี (RGB)",
    "color": "สี (Color)",
}


def list_book_sizes() -> dict[str, dict]:
    """อ่านขนาดหนังสือจาก css/sizes/size_<W>x<H>.css — เรียงจากเล็กไปใหญ่
       field `css` = path relative to CSS_DIR (เช่น "sizes/size_170x228.css")
    """
    if not SIZES_DIR.is_dir():
        return {}

    entries: list[tuple[int, str, dict]] = []
    for css in SIZES_DIR.glob("size_*.css"):
        m = _SIZE_PATTERN.match(css.name)
        if not m:
            continue
        w, h = int(m.group(1)), int(m.group(2))
        key = f"{w}x{h}mm"
        entries.append((w * h, key, {
            "label": f"{w} × {h} mm",
            "css": f"sizes/{css.name}",
        }))

    entries.sort(key=lambda t: (t[0], t[1]))
    return {key: info for _, key, info in entries}


def list_styles() -> list[dict]:
    """อ่านสไตล์จาก css/styles/style_<variant>[_<sub>].css — เรียงตามชื่อ
       field `css` = path relative to CSS_DIR (เช่น "styles/style_bw.css")
       คืน [{key, label, css, allowed_icc}, ...] โดย key = ชื่อไฟล์ไม่รวม .css
    """
    if not STYLES_DIR.is_dir():
        return []
    out = []
    for css in sorted(STYLES_DIR.glob("style_*.css")):
        m = _STYLE_PATTERN.match(css.name)
        if not m:
            continue
        variant = m.group(1).lower()
        suffix = m.group(2)  # อาจเป็น None
        base = _STYLE_LABELS.get(variant, variant.upper())
        label = base if not suffix else f"{base} — {suffix.replace('_', ' ')}"
        out.append({
            "key": css.stem,                            # เช่น "style_bw"
            "label": label,
            "css": f"styles/{css.name}",
            "allowed_icc": _STYLE_ICC_MAP.get(variant, []),
        })
    return out

# ชื่อไฟล์มาตรฐานสำหรับ edge graphics (ตรงกับที่อ้างใน css/edge-graphic.css)
LEFT_GRAPHIC_NAME = "left-graphic-18x234mm-300dpi.png"
RIGHT_GRAPHIC_NAME = "right-graphic-18x234mm-300dpi.png"

# Per-book CSS override — บันทึกไว้ใน input/ (clear_dir ลบหลังใช้)
TEMPLATE_CSS_NAME = "_template_print.css"
TEMPLATE_CSS_MAX_BYTES = 1 * 1024 * 1024   # 1MB hard cap

app = Flask(__name__)
# เพดานขนาด request ทั้งก้อน (zip + edge graphics + template CSS รวมกัน)
# local app คนเดียว → ตั้งสูงได้ แต่ระวัง: zipfile.read() โหลดทั้งไฟล์เข้า RAM
MAX_UPLOAD_MB = 2048  # 2 GB
app.config["MAX_CONTENT_LENGTH"] = MAX_UPLOAD_MB * 1024 * 1024


@app.errorhandler(413)
def _too_large(_err):
    # คืน JSON ภาษาไทยแทน HTML 413 ดิบ → frontend อ่าน .error ได้ตรงๆ
    return jsonify(
        error=f"ไฟล์ที่อัปโหลดใหญ่เกิน {MAX_UPLOAD_MB} MB "
              f"(รวม zip + edge graphics + template CSS) — "
              f"ลดขนาด/บีบอัดรูปในเล่ม หรือแยกไฟล์ แล้วลองใหม่"
    ), 413


# ICC header — bytes 16..19 คือ color space signature (4 ASCII chars)
# Reference: ICC.1:2010 — section 7.2.6
# tuple = (label, mutool -c arg, ICC stream /N, OutputCondition description)
_ICC_CS_TABLE = {
    "GRAY": ("Gray", "gray", 1, "Gray color space"),
    "CMYK": ("CMYK", "cmyk", 4, "CMYK color space"),
    "RGB ": ("RGB",  "rgb",  3, "RGB color space"),
}


def _icc_colorspace(path: Path) -> str:
    """อ่าน 4 bytes ที่ offset 16 ของไฟล์ ICC → คืน color space signature เช่น 'GRAY' / 'CMYK' / 'RGB '"""
    try:
        with open(path, "rb") as f:
            f.seek(16)
            return f.read(4).decode("ascii", errors="replace")
    except OSError:
        return "????"


def list_profiles() -> list[dict]:
    """คืน list ของ {name, colorspace, supported} เรียงตามชื่อ"""
    if not PROFILES_DIR.is_dir():
        return []
    out = []
    for p in sorted(PROFILES_DIR.glob("*.icc")):
        cs = _icc_colorspace(p)
        out.append({
            "name": p.name,
            "colorspace": cs.strip() or "?",
            "supported": cs in _ICC_CS_TABLE,
        })
    return out


def apply_color_pipeline(
    rgb_pdf: Path,
    profile: str,
    profile_cs_raw: str,
    output_dir: Path,
    q: Queue,
) -> Path:
    """แปลง color space + ฝัง ICC โดยรักษา vector text/graphics ไว้

    Pipeline:
      1) mutool recolor -c <gray|rgb|cmyk>  → แปลง color space (preserve vector)
      2) pikepdf inject ICC profile ลง /OutputIntents → ทำให้ไฟล์ valid PDF/X
    """
    label, mutool_arg, channels, condition = _ICC_CS_TABLE[profile_cs_raw]
    final_pdf = output_dir / f"book_{label.lower()}_hq.pdf"
    interim_pdf = output_dir / f".intermediate_{label.lower()}.pdf"

    # 1) mutool recolor
    cmd = ["mutool", "recolor", "-c", mutool_arg, "-o", str(interim_pdf), str(rgb_pdf)]
    rc = stream_subprocess(cmd, cwd=output_dir.parent, output_queue=q)
    if rc != 0:
        if interim_pdf.exists():
            interim_pdf.unlink()
        raise RuntimeError(f"mutool recolor failed (exit {rc})")

    # 2) pikepdf — embed ICC into OutputIntent
    icc_path = PROFILES_DIR / profile
    icc_data = icc_path.read_bytes()
    # ทำชื่อแสดงผลใน Acrobat ให้สวย (เช่น "Dot_Gain_15%.icc" → "Dot Gain 15%")
    display_name = Path(profile).stem.replace("_", " ")
    q.put(f"$ pikepdf: ฝัง ICC {profile} ({channels}-channel) ลง /OutputIntents")
    with pikepdf.open(interim_pdf) as pdf:
        icc_stream = pdf.make_stream(icc_data, {"/N": channels})
        intent = pikepdf.Dictionary({
            "/Type": pikepdf.Name("/OutputIntent"),
            "/S": pikepdf.Name("/GTS_PDFX"),
            "/OutputCondition": pikepdf.String(display_name),
            "/OutputConditionIdentifier": pikepdf.String(display_name),
            "/RegistryName": pikepdf.String(""),
            "/Info": pikepdf.String(display_name),
            "/DestOutputProfile": icc_stream,
        })
        pdf.Root["/OutputIntents"] = pikepdf.Array([intent])
        pdf.save(final_pdf)

    # 3) Post-process — สำหรับ CMYK ต้องบังคับ text สีดำเป็น K100
    #    (มิเช่นนั้นจะกลายเป็น rich black: C+M+Y+K ปนกัน — ไม่ดีต่อ registration ของโรงพิมพ์)
    if profile_cs_raw == "CMYK":
        q.put(f"$ post-process: บังคับ near-black → K100 (สำหรับ CMYK output)")
        enforce_k100_text(final_pdf, q)

    if interim_pdf.exists():
        interim_pdf.unlink()
    return final_pdf


@app.route("/")
def index():
    return render_template(
        "index.html",
        profiles=list_profiles(),
        sizes=list_book_sizes(),
        styles=list_styles(),
    )


def _is_macos_junk(name: str) -> bool:
    """ตัด metadata ที่ macOS Finder ใส่มาใน ZIP (__MACOSX/, ._foo, .DS_Store)"""
    parts = Path(name).parts
    if any(p == "__MACOSX" for p in parts):
        return True
    base = parts[-1] if parts else ""
    return base.startswith("._") or base == ".DS_Store"


def safe_extract_zip(zf: zipfile.ZipFile, target: Path) -> None:
    target = target.resolve()
    for member in zf.infolist():
        if member.is_dir() or _is_macos_junk(member.filename):
            continue
        dest = (target / member.filename).resolve()
        try:
            dest.relative_to(target)
        except ValueError:
            raise ValueError(f"unsafe zip entry: {member.filename}")
        dest.parent.mkdir(parents=True, exist_ok=True)
        with zf.open(member) as src, open(dest, "wb") as out:
            shutil.copyfileobj(src, out)


def find_html(input_dir: Path) -> Path:
    candidate = input_dir / "book.html"
    if candidate.is_file():
        return candidate
    htmls = sorted(
        p for p in input_dir.rglob("*.html")
        if not _is_macos_junk(str(p.relative_to(input_dir)))
    )
    if not htmls:
        raise FileNotFoundError("ไม่พบไฟล์ .html ใน ZIP")
    return htmls[0]


def clear_dir(p: Path) -> None:
    """ลบเนื้อหาในโฟลเดอร์ — แต่เก็บไฟล์ที่ขึ้นต้นด้วย . (เช่น .gitkeep)"""
    if not p.exists():
        p.mkdir(parents=True, exist_ok=True)
        return
    for child in p.iterdir():
        if child.name.startswith("."):
            continue
        if child.is_dir():
            shutil.rmtree(child)
        else:
            child.unlink()


def stream_subprocess(cmd: list[str], cwd: Path, output_queue: Queue) -> int:
    output_queue.put(f"$ {' '.join(cmd)}")
    proc = subprocess.Popen(
        cmd,
        cwd=str(cwd),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
    )
    assert proc.stdout is not None
    for line in proc.stdout:
        output_queue.put(line.rstrip())
    proc.wait()
    return proc.returncode


def build_pipeline(
    zip_bytes: bytes,
    profile: str,
    profile_cs_raw: str,
    size_css: str,
    style_css: str,
    left_graphic: tuple[str, bytes] | None,
    right_graphic: tuple[str, bytes] | None,
    crop_marks: bool,
    pages: str,
    template_css: tuple[str, bytes] | None,
    q: Queue,
) -> None:
    try:
        # 1) เตรียมโฟลเดอร์ + แตก ZIP
        q.put("📦 เตรียม input/ และแตก ZIP ...")
        clear_dir(INPUT_DIR)
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
            safe_extract_zip(zf, INPUT_DIR)

        html_path = find_html(INPUT_DIR)
        q.put(f"✓ พบไฟล์ HTML: {html_path.relative_to(ROOT)}")

        # 2) บันทึก edge graphics — ซ้าย/ขวา/ทั้งคู่/ไม่มี ก็ได้
        if left_graphic is not None:
            ASSETS_DIR.mkdir(parents=True, exist_ok=True)
            (ASSETS_DIR / LEFT_GRAPHIC_NAME).write_bytes(left_graphic[1])
            q.put(f"✓ บันทึก edge graphic ซ้าย: {LEFT_GRAPHIC_NAME}")
        if right_graphic is not None:
            ASSETS_DIR.mkdir(parents=True, exist_ok=True)
            (ASSETS_DIR / RIGHT_GRAPHIC_NAME).write_bytes(right_graphic[1])
            q.put(f"✓ บันทึก edge graphic ขวา: {RIGHT_GRAPHIC_NAME}")

        # 2b) บันทึก template CSS (per-book override) ลง input/ ถ้ามี
        if template_css is not None:
            tpl_path = INPUT_DIR / TEMPLATE_CSS_NAME
            tpl_path.write_bytes(template_css[1])
            q.put(
                f"✓ บันทึก template CSS: {template_css[0]} "
                f"({len(template_css[1])} bytes) → {tpl_path.relative_to(ROOT)}"
            )

        # 2c) ตรวจ CSS ที่อยู่ใน zip (มักเป็น browser CSS — display: flex, vh, box-shadow ฯลฯ)
        #     ไม่โหลดอัตโนมัติ เพราะ browser CSS ไม่ออกแบบมาสำหรับ WeasyPrint
        #     → แจ้ง user ว่าควรใช้ make_style_form generate template CSS แยกสำหรับ print
        zip_css_files = sorted([
            p for p in INPUT_DIR.rglob('*.css')
            if p.name != TEMPLATE_CSS_NAME and not p.name.startswith('.')
        ])
        if zip_css_files and template_css is None:
            names = ", ".join(p.relative_to(INPUT_DIR).as_posix() for p in zip_css_files)
            q.put(
                f"⚠ พบ CSS ใน zip ({names}) แต่ไม่ได้โหลด — "
                f"browser CSS ไม่เข้ากับ WeasyPrint (flex/vh/box-shadow)\n"
                f"  → ใช้ make_style_form generate template-print.css "
                f"แล้ว upload ผ่านช่อง 'Template CSS ส่วนตัว'"
            )

        # 3) Step 1/3 — sync_toc
        # เขียน synced ไว้ข้างไฟล์ต้นฉบับ เพื่อให้ relative path (./images/...) resolve ถูก
        # ⚠ synced_html = "editor-safe": sync แค่ TOC, รูปยังเป็น % → เปิดใน editor ต่อได้
        #    print transforms (normalize %→pt / callout / gradient) ทำบน print_html แยก
        #    → ไม่เขียน px ทับไฟล์ที่ user เปิดใน editor (กันรูปเกินกรอบ)
        q.put("\n[1/3] sync_toc.py")
        synced_html = html_path.with_name(html_path.stem + ".synced.html")
        rc = stream_subprocess(
            ["python3", str(SYNC_SCRIPT), str(html_path), "-o", str(synced_html)],
            cwd=ROOT, output_queue=q,
        )
        if rc != 0:
            q.put(json.dumps({"__error__": f"sync_toc failed (exit {rc})"}))
            return

        # 3b) normalize_images — scale crop <img> ที่เกิน text column ให้พอดี (uniform)
        #     อ่านจาก synced_html (% editor-safe) → เขียน print_html (px พร้อมพิมพ์)
        #     print_html อยู่ใน input/ เพื่อให้ ./images/ resolve ถูก แต่เป็นไฟล์ build
        #     (อย่าเปิดใน editor — รูปเป็น pt จะเกินกรอบ)
        print_html = html_path.with_name(html_path.stem + ".print.html")
        max_col_pt = compute_text_column_pt(size_css)
        q.put(f"\n[1b/3] normalize_images.py (max-col {max_col_pt:.1f}pt)")
        rc = stream_subprocess(
            ["python3", str(NORMALIZE_SCRIPT), str(synced_html),
             "-o", str(print_html), "--max-col-pt", f"{max_col_pt:.2f}"],
            cwd=ROOT, output_queue=q,
        )
        if rc != 0:
            q.put(json.dumps({"__error__": f"normalize_images failed (exit {rc})"}))
            return

        # 3c) fix_callout — เติม fill="none" stroke="transparent" ลง <path class="img-line-hit">
        #     ⚠ จำเป็น: WeasyPrint v68.x ไม่รองรับ fill/stroke เป็น CSS property
        #              → CSS override ไม่ทำงาน → ต้องแก้ inline ที่ HTML
        #     idempotent — รันซ้ำได้ + ปลอดภัยถ้า editor แก้แล้ว
        q.put("\n[1c/3] fix_callout.py")
        rc = stream_subprocess(
            ["python3", str(FIX_CALLOUT_SCRIPT), str(print_html), "-o", str(print_html)],
            cwd=ROOT, output_queue=q,
        )
        if rc != 0:
            q.put(json.dumps({"__error__": f"fix_callout failed (exit {rc})"}))
            return

        # 3d) fix_gradient — แทน inline CSS gradient ด้วยสีพื้น
        #     ⚠ จำเป็น: mutool recolor 1.27.2 segfault (exit -11) ถ้า PDF มี gradient
        #              gradient จาก inline style ไม่ผูกกับ @media → ต้องแก้ที่ HTML
        #     idempotent — รันซ้ำได้ + ปลอดภัยถ้าไม่มี gradient
        q.put("\n[1d/3] fix_gradient.py")
        rc = stream_subprocess(
            ["python3", str(FIX_GRADIENT_SCRIPT), str(print_html), "-o", str(print_html)],
            cwd=ROOT, output_queue=q,
        )
        if rc != 0:
            q.put(json.dumps({"__error__": f"fix_gradient failed (exit {rc})"}))
            return

        # 4) Step 2/3 — weasyprint
        q.put("\n[2/3] weasyprint")
        rgb_pdf = OUTPUT_DIR / "book_rgb_bw_nomarks.pdf"
        (ROOT / ".weasy-cache").mkdir(parents=True, exist_ok=True)
        # Order: size → style (base) → default-print (auto-fallback) → template (user override)
        #        → graphics → no-marks
        # ⚠ ไม่โหลด zip CSS อัตโนมัติ — มักเป็น browser CSS (flex/vh/box-shadow) ไม่เข้ากับ WeasyPrint
        weasy_cmd: list[str] = [
            "weasyprint",
            "-s", f"css/{size_css}",
            "-s", f"css/{style_css}",
        ]
        # โหลด print defaults เสมอ (layout baseline: image 100%, callout fix ฯลฯ)
        # → user template สามารถ override จุดที่ต้องการ แต่ image fix ไม่หาย
        if DEFAULT_PRINT_CSS.is_file():
            weasy_cmd += ["-s", str(DEFAULT_PRINT_CSS.relative_to(ROOT))]
            q.put(f"✓ baseline: template/{DEFAULT_PRINT_CSS.name}")
        if template_css is not None:
            weasy_cmd += ["-s", f"input/{TEMPLATE_CSS_NAME}"]
        if left_graphic is not None:
            weasy_cmd += ["-s", "css/edge-graphic-left.css"]
        if right_graphic is not None:
            weasy_cmd += ["-s", "css/edge-graphic-right.css"]
        if not crop_marks:
            weasy_cmd += ["-s", "css/no-marks.css"]
        weasy_cmd += [
            "--pdf-variant", "pdf/x-4",
            # ตัด --optimize-images -j 90 ออก → ไม่ re-encode รูป → ฝัง original bytes
            # (PDF โตขึ้น ~30-50% แต่ภาพคมเท่าต้นฉบับ)
            "-D", "300",
            "-c", ".weasy-cache",
            str(print_html),
            str(rgb_pdf),
        ]
        rc = stream_subprocess(weasy_cmd, cwd=ROOT, output_queue=q)
        if rc != 0:
            q.put(json.dumps({"__error__": f"weasyprint failed (exit {rc})"}))
            return
        q.put(f"✓ {rgb_pdf.relative_to(ROOT)}")

        # 5) Step 3/3 — แปลง color space + ฝัง ICC (mutool + pikepdf)
        label = _ICC_CS_TABLE[profile_cs_raw][0]
        q.put(f"\n[3/3] mutool recolor + pikepdf (ICC: {profile}, color space: {label})")
        try:
            final_pdf = apply_color_pipeline(
                rgb_pdf, profile, profile_cs_raw, OUTPUT_DIR, q,
            )
        except Exception as e:
            q.put(json.dumps({"__error__": f"color pipeline failed: {e}"}))
            return

        # 6) Optional — ตัดหน้าตามที่ user ระบุด้วย mutool clean
        if pages:
            q.put(f"\n[+] ตัดหน้าตามที่ระบุ: {pages}")
            extracted = OUTPUT_DIR / f"_extracted_{final_pdf.name}"
            rc = stream_subprocess(
                ["mutool", "clean", str(final_pdf), str(extracted), pages],
                cwd=ROOT, output_queue=q,
            )
            if rc != 0:
                if extracted.exists():
                    extracted.unlink()
                q.put(json.dumps({"__error__": f"mutool clean (extract pages) failed (exit {rc})"}))
                return
            # แทน final_pdf ด้วยไฟล์ที่ตัดหน้าแล้ว
            final_pdf.unlink()
            extracted.rename(final_pdf)
            q.put(f"✓ ตัดหน้า '{pages}' เสร็จ → {final_pdf.relative_to(ROOT)}")

        q.put(f"\n✓ เสร็จสมบูรณ์ → {final_pdf.relative_to(ROOT)}")
        q.put(json.dumps({
            "__done__": True,
            "download": f"/download/{final_pdf.name}",
            "intermediate": f"/download/{rgb_pdf.name}",
            "colorspace": _ICC_CS_TABLE[profile_cs_raw][0],  # "Gray" / "CMYK" / "RGB"
            "pages": pages or None,
        }))
    except Exception as e:
        q.put(json.dumps({"__error__": f"{type(e).__name__}: {e}"}))


@app.route("/build", methods=["POST"])
def build():
    if "zipfile" not in request.files or not request.files["zipfile"].filename:
        return jsonify(error="ต้องอัปโหลดไฟล์ ZIP"), 400

    profile = request.form.get("profile", "")
    profiles_by_name = {p["name"]: p for p in list_profiles()}
    if profile not in profiles_by_name:
        return jsonify(error=f"โปรไฟล์สีไม่ถูกต้อง: {profile}"), 400
    profile_cs = profiles_by_name[profile]["colorspace"]
    profile_cs_raw = profile_cs.ljust(4)  # คืน signature 4 ตัวอักษรสำหรับ lookup
    if profile_cs_raw not in _ICC_CS_TABLE:
        return jsonify(error=f"โปรไฟล์สี '{profile}' ใช้ color space ที่ไม่รองรับ: {profile_cs!r}"), 400

    sizes = list_book_sizes()
    size_key = request.form.get("size", "")
    if size_key not in sizes:
        return jsonify(error=f"ขนาดหนังสือไม่ถูกต้อง: {size_key}"), 400
    size_css = sizes[size_key]["css"]

    styles_by_key = {s["key"]: s for s in list_styles()}
    style_key = request.form.get("style", "")
    if style_key not in styles_by_key:
        return jsonify(error=f"สไตล์ไม่ถูกต้อง: {style_key}"), 400
    style_info = styles_by_key[style_key]
    style_css = style_info["css"]

    # ตรวจ ICC ↔ style compatibility (allowed_icc ว่าง = ไม่จำกัด)
    allowed_icc = style_info["allowed_icc"]
    if allowed_icc and profile_cs_raw not in allowed_icc:
        cs_label = profile_cs_raw.strip() or "?"
        allowed_label = ", ".join(s.strip() for s in allowed_icc)
        return jsonify(
            error=f"สไตล์ '{style_info['label']}' ใช้ได้กับ ICC color space: {allowed_label} "
                  f"แต่ ICC ที่เลือกเป็น {cs_label}"
        ), 400

    zip_bytes = request.files["zipfile"].read()

    def read_optional(field: str) -> tuple[str, bytes] | None:
        f = request.files.get(field)
        if f is None or not f.filename:
            return None
        return (f.filename, f.read())

    left_graphic = read_optional("left_graphic")
    right_graphic = read_optional("right_graphic")
    crop_marks = request.form.get("crop_marks") is not None

    # Per-book CSS override — ไม่บังคับ
    template_css = read_optional("template_css")
    if template_css is not None:
        fname, data = template_css
        if not fname.lower().endswith(".css"):
            return jsonify(
                error=f"ไฟล์ template ต้องเป็น .css เท่านั้น (ได้รับ: {fname})"
            ), 400
        if len(data) > TEMPLATE_CSS_MAX_BYTES:
            mb = len(data) / (1024 * 1024)
            return jsonify(
                error=f"ไฟล์ template ใหญ่เกินกำหนด {mb:.1f}MB "
                      f"(สูงสุด {TEMPLATE_CSS_MAX_BYTES // (1024*1024)}MB)"
            ), 400

    # หน้าที่ต้องการ — ไม่บังคับ ถ้าไม่ใส่ = ทั้งเล่ม
    pages_input = (request.form.get("pages") or "").strip()
    if pages_input:
        if not _PAGES_PATTERN.match(pages_input):
            return jsonify(
                error=f"รูปแบบหน้าไม่ถูกต้อง: '{pages_input}' — ตัวอย่าง: 1,4-8,12 หรือ 4-20"
            ), 400
        pages_clean = re.sub(r"\s+", "", pages_input)
    else:
        pages_clean = ""

    # log สิ่งที่ได้รับจริง — เพื่อ debug
    print(
        f"[build] size={size_key!r} → {size_css!r}  "
        f"style={style_key!r} → {style_css!r}  "
        f"profile={profile!r} ({profile_cs})  "
        f"zip={len(zip_bytes)} bytes  "
        f"left={'✓' if left_graphic else '–'}  "
        f"right={'✓' if right_graphic else '–'}  "
        f"template={'✓ ' + template_css[0] if template_css else '–'}  "
        f"crop_marks={crop_marks}  "
        f"pages={pages_clean!r}",
        flush=True,
    )

    q: Queue = Queue()
    worker = threading.Thread(
        target=build_pipeline,
        args=(zip_bytes, profile, profile_cs_raw, size_css, style_css,
              left_graphic, right_graphic, crop_marks, pages_clean, template_css, q),
        daemon=True,
    )
    worker.start()

    def generate():
        while True:
            try:
                item = q.get(timeout=0.5)
            except Empty:
                if not worker.is_alive():
                    return
                continue
            yield item + "\n"

    return Response(generate(), mimetype="text/plain; charset=utf-8")


@app.route("/download/<path:name>")
def download(name: str):
    safe = (OUTPUT_DIR / name).resolve()
    if not str(safe).startswith(str(OUTPUT_DIR.resolve()) + "/") or not safe.is_file():
        abort(404)
    return send_file(safe, as_attachment=True)


@app.route("/clear-cache", methods=["POST"])
def clear_cache():
    """ลบ .weasy-cache/ ทิ้ง — ใช้เมื่อสงสัยว่า cache เสียทำให้ build ผลแปลก"""
    cache_dir = ROOT / ".weasy-cache"
    if not cache_dir.exists():
        return jsonify({"ok": True, "files": 0, "bytes": 0, "message": "ไม่มี cache อยู่แล้ว"})
    files = 0
    total_bytes = 0
    for p in cache_dir.rglob("*"):
        if p.is_file():
            files += 1
            try:
                total_bytes += p.stat().st_size
            except OSError:
                pass
    try:
        shutil.rmtree(cache_dir)
    except OSError as e:
        return jsonify({"ok": False, "error": str(e)}), 500
    mb = total_bytes / (1024 * 1024)
    return jsonify({
        "ok": True,
        "files": files,
        "bytes": total_bytes,
        "message": f"ลบ cache แล้ว: {files} ไฟล์ ({mb:.1f} MB)",
    })


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5050, debug=False, threaded=True)
