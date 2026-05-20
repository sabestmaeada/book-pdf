#!/usr/bin/env bash
# Launcher สำหรับ UI สร้าง PDF หนังสือ
# - สร้าง venv (ครั้งแรกครั้งเดียว)
# - ติดตั้ง dependencies (Flask, beautifulsoup4)
# - ตรวจ weasyprint / gs ในระบบ
# - เปิด Flask + browser

set -e

cd "$(dirname "$0")"

PORT="${PORT:-5050}"
VENV=".venv"

# --- 1) Python venv ---
if [ ! -d "$VENV" ]; then
  echo "→ สร้าง virtualenv ที่ $VENV ..."
  python3 -m venv "$VENV"
fi

# shellcheck disable=SC1091
source "$VENV/bin/activate"

# --- 2) ติดตั้ง dependencies ---
if [ ! -f "$VENV/.deps_installed" ] || [ "requirements.txt" -nt "$VENV/.deps_installed" ]; then
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
