#!/usr/bin/env bash
# Launcher สำหรับ UI สร้าง PDF หนังสือ
# - สร้าง venv (ครั้งแรกครั้งเดียว)
# - ติดตั้ง dependencies (Flask, beautifulsoup4)
# - ตรวจ weasyprint / gs ในระบบ
# - เปิด Flask + browser

set -e

cd "$(dirname "$0")"

# --- 0) Add Homebrew to PATH (สำคัญเมื่อรันผ่าน .app / Finder ที่ไม่โหลด .zprofile) ---
# Apple Silicon: /opt/homebrew/bin  |  Intel: /usr/local/bin
for brew_prefix in /opt/homebrew /usr/local; do
  if [ -x "$brew_prefix/bin/brew" ]; then
    eval "$($brew_prefix/bin/brew shellenv)"
    break
  fi
done

PORT="${PORT:-5050}"
VENV=".venv"

# --- 1) Python venv ---
# venv ใช้ symlink ไป Python ของเครื่องที่สร้าง — copy ข้ามเครื่องแล้วใช้ไม่ได้
# ตรวจว่า .venv/bin/python3 เรียกใช้ได้จริง ถ้าไม่ได้ → สร้างใหม่
VENV_PY="$VENV/bin/python3"
if [ -d "$VENV" ] && { [ ! -x "$VENV_PY" ] || ! "$VENV_PY" -c '' 2>/dev/null; }; then
  echo "→ venv เสีย / มาจากเครื่องอื่น — สร้างใหม่ ..."
  rm -rf "$VENV"
fi

if [ ! -d "$VENV" ]; then
  echo "→ สร้าง virtualenv ที่ $VENV ..."
  python3 -m venv "$VENV"
fi

# shellcheck disable=SC1091
source "$VENV/bin/activate"

# --- 2) ติดตั้ง dependencies ---
# verify import จริง — flag file อย่างเดียวเชื่อไม่ได้เมื่อ venv ถูก copy ข้ามเครื่อง
need_install=0
if [ ! -f "$VENV/.deps_installed" ] || [ "requirements.txt" -nt "$VENV/.deps_installed" ]; then
  need_install=1
elif ! python3 -c 'import flask, bs4, pikepdf' 2>/dev/null; then
  echo "→ ตรวจไม่พบ library (Flask/bs4/pikepdf) — ติดตั้งใหม่ ..."
  need_install=1
fi
if [ "$need_install" -eq 1 ]; then
  echo "→ ติดตั้ง dependencies ..."
  pip install --upgrade pip --quiet
  pip install -r requirements.txt --quiet
  touch "$VENV/.deps_installed"
fi

# --- 3) ตรวจ external tools ---
missing=0
if ! command -v weasyprint >/dev/null 2>&1; then
  echo "⚠ ไม่พบ weasyprint  → ติดตั้งด้วย: brew install weasyprint  หรือ  pip install weasyprint"
  missing=1
fi
if ! command -v mutool >/dev/null 2>&1; then
  echo "⚠ ไม่พบ mutool (MuPDF)  → ติดตั้งด้วย: brew install mupdf-tools"
  missing=1
fi
if [ "$missing" -eq 1 ]; then
  echo ""
  echo "ติดตั้งให้ครบก่อนใช้งาน — UI จะเปิดต่อไปได้แต่ build จะล้มเหลว"
  echo ""
fi

# --- 4) เปิด browser หลัง server พร้อม ---
URL="http://localhost:$PORT"
(
  for _ in 1 2 3 4 5 6 7 8 9 10; do
    sleep 0.6
    if curl -sf -o /dev/null "$URL"; then
      open "$URL"
      break
    fi
  done
) &

echo ""
echo "🚀 UI พร้อมที่ $URL"
echo "   (กด Ctrl+C เพื่อปิด)"
echo ""

exec python3 ui/app.py
