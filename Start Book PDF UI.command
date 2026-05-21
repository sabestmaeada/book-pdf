#!/usr/bin/env bash
# Book PDF UI — friendly launcher
# ดับเบิลคลิกใน Finder → Terminal เปิด → รัน start_ui.sh

# เปลี่ยน Terminal title bar
printf '\033]0;Book PDF UI\007'

cd "$(dirname "$0")"

clear

# ──────────── สีและไฮไลต์ใน Terminal ────────────
BOLD='\033[1m'
CYAN='\033[36m'
GREEN='\033[32m'
YELLOW='\033[33m'
DIM='\033[2m'
RESET='\033[0m'

# ──────────── banner ────────────
printf "${CYAN}${BOLD}"
cat <<'BANNER'
╔════════════════════════════════════════════════════╗
║                                                    ║
║           📚  Book PDF UI                          ║
║                                                    ║
║   เครื่องมือสร้าง PDF หนังสือจาก HTML              ║
║                                                    ║
╚════════════════════════════════════════════════════╝
BANNER
printf "${RESET}"

echo ""
printf "${GREEN}${BOLD}🚀 กำลังเริ่ม Server...${RESET}\n"
printf "${DIM}   (ครั้งแรกอาจใช้เวลา ~1 นาที เพื่อติดตั้ง dependencies)${RESET}\n"
echo ""
printf "${BOLD}📝 หลังจาก server พร้อม → Browser จะเปิดเอง${RESET}\n"
printf "${YELLOW}⛔ ปิดหน้าต่างนี้ (หรือกด Ctrl+C) เพื่อหยุดการทำงาน${RESET}\n"
echo ""
printf "${DIM}──────────────────────────────────────────────────${RESET}\n"
echo ""

# รัน start_ui.sh แทนตัวเอง (preserve terminal title + banner)
exec ./start_ui.sh
