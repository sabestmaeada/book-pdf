#!/usr/bin/env python3
"""
check_icc.py — ตรวจสอบ ICC profile ที่ฝังใน PDF

Usage:
    python3 check_icc.py <pdf_file> [<pdf_file2> ...]
    python3 check_icc.py output/book_gray_hq.pdf
"""

import hashlib
import os
import sys
from pathlib import Path

# ถ้าไม่มี pikepdf ใน Python ปัจจุบัน → re-exec ด้วย venv Python ของโปรเจกต์
try:
    import pikepdf
except ImportError:
    _venv_py = Path(__file__).resolve().parent / ".venv" / "bin" / "python3"
    if _venv_py.is_file() and sys.executable != str(_venv_py):
        os.execv(str(_venv_py), [str(_venv_py), __file__, *sys.argv[1:]])
    sys.stderr.write(
        "error: pikepdf ไม่ติดตั้ง\n"
        "  รัน './start_ui.sh' หนึ่งครั้งเพื่อสร้าง venv และติดตั้ง dependencies\n"
        "  หรือ: pip install pikepdf\n"
    )
    sys.exit(1)

# ICC color space signature (bytes 16..19 ของ ICC profile header)
_ICC_CS_LABEL = {
    b"GRAY": "GRAY (1-channel grayscale)",
    b"CMYK": "CMYK (4-channel)",
    b"RGB ": "RGB (3-channel)",
    b"LAB ": "Lab",
    b"XYZ ": "XYZ",
}

PROFILES_DIR = Path(__file__).parent / "profiles"


def _identify_known_profile(icc_bytes: bytes) -> str | None:
    """เทียบ ICC bytes กับไฟล์ใน profiles/ — ถ้า match คืนชื่อไฟล์"""
    if not PROFILES_DIR.is_dir():
        return None
    target_hash = hashlib.md5(icc_bytes).hexdigest()
    for p in PROFILES_DIR.glob("*.icc"):
        if hashlib.md5(p.read_bytes()).hexdigest() == target_hash:
            return p.name
    return None


def _check_one(pdf_path: Path) -> None:
    print(f"\n📄 {pdf_path}")
    print(f"   ขนาด: {pdf_path.stat().st_size / 1024:.1f} KB")

    try:
        with pikepdf.open(pdf_path) as pdf:
            oi = pdf.Root.get("/OutputIntents")
            if not oi:
                print("   ❌ ไม่มี /OutputIntents → ไม่ได้ฝัง ICC profile")
                return

            for i, intent in enumerate(oi):
                print(f"\n   OutputIntent[{i}]:")
                print(f"      Subtype       : {intent.get('/S', '?')}")
                print(f"      Condition     : {intent.get('/OutputCondition', '–')}")
                print(f"      Identifier    : {intent.get('/OutputConditionIdentifier', '–')}")
                print(f"      Info          : {intent.get('/Info', '–')}")

                prof = intent.get("/DestOutputProfile")
                if prof is None:
                    print(f"      ICC profile   : ❌ ไม่ฝัง (มีแค่ metadata)")
                    continue

                # decode stream (auto-handle FlateDecode)
                icc = bytes(prof.read_bytes())
                n = int(prof.get("/N", 0))

                if len(icc) >= 20:
                    sig = icc[16:20]
                    cs_label = _ICC_CS_LABEL.get(sig, f"unknown ({sig!r})")
                else:
                    cs_label = "(ไฟล์เสีย — สั้นเกินไป)"

                print(f"      ICC channels  : /N = {n}")
                print(f"      ICC color sp. : {cs_label}")
                print(f"      ICC data size : {len(icc):,} bytes")
                print(f"      ICC MD5       : {hashlib.md5(icc).hexdigest()}")

                match = _identify_known_profile(icc)
                if match:
                    print(f"      ✅ ตรงกับ      : profiles/{match}")
                else:
                    print(f"      ⚠ ไม่ตรงกับไฟล์ใดใน profiles/")
    except pikepdf.PdfError as e:
        print(f"   ❌ อ่าน PDF ไม่ได้: {e}")


def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__.strip())
        return 1

    for arg in sys.argv[1:]:
        p = Path(arg)
        if not p.is_file():
            print(f"❌ ไม่พบไฟล์: {arg}")
            continue
        _check_one(p)
    return 0


if __name__ == "__main__":
    sys.exit(main())
