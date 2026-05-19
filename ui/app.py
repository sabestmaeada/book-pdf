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

from flask import Flask, Response, abort, jsonify, render_template, request, send_file

ROOT = Path(__file__).parent.parent.resolve()
INPUT_DIR = ROOT / "input"
OUTPUT_DIR = ROOT / "output"
ASSETS_DIR = ROOT / "assets"
CSS_DIR = ROOT / "css"
PROFILES_DIR = ROOT / "profiles"
SYNC_SCRIPT = ROOT / "sync_toc.py"

# Auto-detect ขนาดหนังสือจากชื่อไฟล์ใน css/
# Pattern: weasyprint_print_<variant>_<W>x<H>.css
_SIZE_PATTERN = re.compile(r"^weasyprint_print_([a-z0-9]+)_(\d+)x(\d+)\.css$", re.IGNORECASE)
# variants ที่ "ไม่ต้องโชว์ในวงเล็บ" (default — ไม่มี suffix)
_DEFAULT_VARIANTS = {"bw", "mono"}
_VARIANT_LABELS = {
    "color": "สี",
    "cmyk": "CMYK",
}


def list_book_sizes() -> dict[str, dict]:
    """อ่านขนาดหนังสือจากชื่อไฟล์ CSS — เรียงจากเล็กไปใหญ่ตามพื้นที่กระดาษ"""
    if not CSS_DIR.is_dir():
        return {}

    entries: list[tuple[int, str, dict]] = []
    for css in CSS_DIR.glob("weasyprint_print_*.css"):
        m = _SIZE_PATTERN.match(css.name)
        if not m:
            continue
        variant, w, h = m.group(1).lower(), int(m.group(2)), int(m.group(3))
        key = f"{variant}_{w}x{h}mm"
        if variant in _DEFAULT_VARIANTS:
            label = f"{w} × {h} mm"
        else:
            suffix = _VARIANT_LABELS.get(variant, variant)
            label = f"{w} × {h} mm ({suffix})"
        entries.append((w * h, key, {
            "label": label,
            "css": css.name,
        }))

    entries.sort(key=lambda t: (t[0], t[1]))
    return {key: info for _, key, info in entries}

# ชื่อไฟล์มาตรฐานสำหรับ edge graphics (ตรงกับที่อ้างใน css/edge-graphic.css)
LEFT_GRAPHIC_NAME = "left-graphic-18x234mm-300dpi.png"
RIGHT_GRAPHIC_NAME = "right-graphic-18x234mm-300dpi.png"

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 500 * 1024 * 1024  # 500 MB


# ICC header — bytes 16..19 คือ color space signature (4 ASCII chars)
# Reference: ICC.1:2010 — section 7.2.6
_ICC_CS_TO_DEVICE = {
    "GRAY": ("Gray", "DeviceGray"),
    "CMYK": ("CMYK", "DeviceCMYK"),
    "RGB ": ("RGB",  "DeviceRGB"),
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
            "supported": cs in _ICC_CS_TO_DEVICE,
        })
    return out


@app.route("/")
def index():
    return render_template(
        "index.html",
        profiles=list_profiles(),
        sizes=list_book_sizes(),
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
    if not p.exists():
        p.mkdir(parents=True, exist_ok=True)
        return
    for child in p.iterdir():
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
    css_name: str,
    left_graphic: tuple[str, bytes] | None,
    right_graphic: tuple[str, bytes] | None,
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

        # 2) บันทึก edge graphics ถ้ามี (ต้องครบทั้งซ้าย+ขวา)
        use_edge_graphic = left_graphic is not None and right_graphic is not None
        if use_edge_graphic:
            ASSETS_DIR.mkdir(parents=True, exist_ok=True)
            (ASSETS_DIR / LEFT_GRAPHIC_NAME).write_bytes(left_graphic[1])
            (ASSETS_DIR / RIGHT_GRAPHIC_NAME).write_bytes(right_graphic[1])
            q.put(f"✓ บันทึก edge graphics: {LEFT_GRAPHIC_NAME}, {RIGHT_GRAPHIC_NAME}")
        elif left_graphic or right_graphic:
            q.put("⚠ ต้องอัปโหลด edge graphic ทั้งซ้ายและขวา → ข้ามการใช้กราฟิกขอบหน้า")

        # 3) Step 1/3 — sync_toc
        # เขียน synced ไว้ข้างไฟล์ต้นฉบับ เพื่อให้ relative path (./images/...) resolve ถูก
        q.put("\n[1/3] sync_toc.py")
        synced_html = html_path.with_name(html_path.stem + ".synced.html")
        rc = stream_subprocess(
            ["python3", str(SYNC_SCRIPT), str(html_path), "-o", str(synced_html)],
            cwd=ROOT, output_queue=q,
        )
        if rc != 0:
            q.put(json.dumps({"__error__": f"sync_toc failed (exit {rc})"}))
            return

        # 4) Step 2/3 — weasyprint
        q.put("\n[2/3] weasyprint")
        rgb_pdf = OUTPUT_DIR / "book_rgb_bw_nomarks.pdf"
        weasy_cmd: list[str] = ["weasyprint", "-s", f"css/{css_name}"]
        if use_edge_graphic:
            weasy_cmd += ["-s", "css/edge-graphic.css"]
        weasy_cmd += [
            "-s", "css/no-marks.css",
            "--pdf-variant", "pdf/x-4",
            "--optimize-images", "-j", "90", "-D", "300",
            "-c", ".weasy-cache",
            str(synced_html),
            str(rgb_pdf),
        ]
        rc = stream_subprocess(weasy_cmd, cwd=ROOT, output_queue=q)
        if rc != 0:
            q.put(json.dumps({"__error__": f"weasyprint failed (exit {rc})"}))
            return
        q.put(f"✓ {rgb_pdf.relative_to(ROOT)}")

        # 5) Step 3/3 — ghostscript
        # เลือก strategy + process color model ให้ match กับ ICC profile
        strategy, process_model = _ICC_CS_TO_DEVICE[profile_cs_raw]
        # ตั้งชื่อไฟล์ output ตาม color space เพื่อไม่ทับกัน
        final_pdf = OUTPUT_DIR / f"book_{strategy.lower()}_hq.pdf"
        q.put(f"\n[3/3] ghostscript (ICC: {profile}, color space: {strategy})")
        gs_cmd = [
            "gs", "-dNOSAFER", "-dBATCH", "-dNOPAUSE",
            "-sDEVICE=pdfwrite",
            f"-sOutputFile={final_pdf}",
            "-dPDFX", "-dCompatibilityLevel=1.6",
            "-dPDFSETTINGS=/prepress",
            f"-sColorConversionStrategy={strategy}",
            f"-dProcessColorModel=/{process_model}",
            "-dBlackText=true",
            "-dDownsampleColorImages=false",
            "-dDownsampleGrayImages=false",
            "-dDownsampleMonoImages=false",
            "-dPreserveAnnots=true",
            "-dPreserveMarkedContent=true",
            "-dPreserveEPSInfo=true",
            f"-sOutputICCProfile=profiles/{profile}",
            str(rgb_pdf),
        ]
        rc = stream_subprocess(gs_cmd, cwd=ROOT, output_queue=q)
        if rc != 0:
            q.put(json.dumps({"__error__": f"ghostscript failed (exit {rc})"}))
            return

        q.put(f"\n✓ เสร็จสมบูรณ์ → {final_pdf.relative_to(ROOT)}")
        q.put(json.dumps({
            "__done__": True,
            "download": f"/download/{final_pdf.name}",
            "intermediate": f"/download/{rgb_pdf.name}",
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
    if profile_cs_raw not in _ICC_CS_TO_DEVICE:
        return jsonify(error=f"โปรไฟล์สี '{profile}' ใช้ color space ที่ไม่รองรับ: {profile_cs!r}"), 400

    sizes = list_book_sizes()
    size_key = request.form.get("size", "")
    if size_key not in sizes:
        return jsonify(error=f"ขนาดหนังสือไม่ถูกต้อง: {size_key}"), 400
    css_name = sizes[size_key]["css"]

    zip_bytes = request.files["zipfile"].read()

    def read_optional(field: str) -> tuple[str, bytes] | None:
        f = request.files.get(field)
        if f is None or not f.filename:
            return None
        return (f.filename, f.read())

    left_graphic = read_optional("left_graphic")
    right_graphic = read_optional("right_graphic")

    # log สิ่งที่ได้รับจริง — เพื่อ debug
    print(
        f"[build] size={size_key!r} → css={css_name!r}  "
        f"profile={profile!r} ({profile_cs})  "
        f"zip={len(zip_bytes)} bytes  "
        f"left={'✓' if left_graphic else '–'}  "
        f"right={'✓' if right_graphic else '–'}",
        flush=True,
    )

    q: Queue = Queue()
    worker = threading.Thread(
        target=build_pipeline,
        args=(zip_bytes, profile, profile_cs_raw, css_name, left_graphic, right_graphic, q),
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


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5050, debug=False, threaded=True)
