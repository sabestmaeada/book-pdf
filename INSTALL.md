# การติดตั้ง Prerequisites บน macOS

คู่มือติดตั้งเครื่องมือที่จำเป็นสำหรับ pipeline สร้าง PDF — **Homebrew + WeasyPrint + Ghostscript**

ใช้เวลาประมาณ 10–15 นาที (ขึ้นกับความเร็วเน็ต)

---

## 1. ตรวจระบบก่อนเริ่ม

เปิด **Terminal** (กด ⌘ + Space → พิมพ์ "Terminal") แล้วรันเช็คเวอร์ชัน macOS:

```bash
sw_vers
```

แนะนำ **macOS 12 (Monterey) ขึ้นไป** — รุ่นเก่ากว่านี้ Homebrew อาจไม่รองรับเครื่องมือเวอร์ชันใหม่

เช็คชนิดเครื่อง:
```bash
uname -m
# arm64  → Apple Silicon (M1/M2/M3/M4)
# x86_64 → Intel Mac
```

---

## 2. ติดตั้ง Xcode Command Line Tools

Homebrew ต้องใช้ compiler ของ Apple ติดตั้งครั้งเดียว:

```bash
xcode-select --install
```

ถ้าขึ้น "already installed" = มีอยู่แล้ว ข้ามได้

> หน้าต่าง popup จะขึ้นมาให้ติดตั้ง กดยอมรับและรอสัก 5–10 นาที

---

## 3. ติดตั้ง Homebrew

Homebrew (`brew`) คือ package manager มาตรฐานของ macOS — ใช้ติดตั้งเครื่องมือ command-line ต่างๆ

รันคำสั่ง official จาก [brew.sh](https://brew.sh):

```bash
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
```

ระหว่างติดตั้ง จะถาม **password ของเครื่อง** — กรอกแล้ว Enter (จะไม่เห็นตัวอักษรเวลาพิมพ์ ปกติครับ)

### หลังติดตั้ง — เพิ่ม brew ลง PATH

**Apple Silicon (M1/M2/M3/M4):**
```bash
echo 'eval "$(/opt/homebrew/bin/brew shellenv)"' >> ~/.zprofile
eval "$(/opt/homebrew/bin/brew shellenv)"
```

**Intel Mac:**
```bash
echo 'eval "$(/usr/local/bin/brew shellenv)"' >> ~/.zprofile
eval "$(/usr/local/bin/brew shellenv)"
```

ตรวจว่าใช้งานได้:
```bash
brew --version
# ควรขึ้น: Homebrew x.x.x
```

---

## 4. ติดตั้ง WeasyPrint

WeasyPrint แปลง HTML/CSS → PDF — ติดตั้งผ่าน brew ได้สะดวกสุด (รวม native libraries ทั้งหมดให้แล้ว: Pango, Cairo, GDK-PixBuf, libffi):

```bash
brew install weasyprint
```

ใช้เวลา 3–5 นาที (ดาวน์โหลด + compile dependencies เยอะ)

ตรวจ:
```bash
weasyprint --version
# ทดสอบกับ 68.x ขึ้นไป
```

> **ทางเลือกผ่าน pip** — `pip install weasyprint` ก็ได้ แต่ต้อง `brew install pango cairo gdk-pixbuf libffi` เองก่อน ไม่แนะนำ ยุ่งกว่า

---

## 5. ติดตั้ง MuPDF tools

`mutool` (จาก MuPDF) ใช้แปลง color space (RGB → Gray/CMYK) โดย **รักษา text เป็น vector** ไม่แปลงเป็นรูปภาพ:

```bash
brew install mupdf-tools
```

ใช้เวลา 1–2 นาที

ตรวจ:
```bash
mutool --version
# ทดสอบกับ 1.27 ขึ้นไป
```

> **ทำไมไม่ใช้ Ghostscript** — `gs` มักจะ rasterize PDF ที่มี CID Thai/CJK fonts ตอนแปลง color space ทำให้ข้อความกลายเป็นภาพ scale ไม่ได้, search/copy ไม่ได้ และไฟล์ใหญ่ขึ้นมาก MuPDF preserve vector ครบ + เร็วกว่ามาก (~1s vs 30s)

---

## 6. ตรวจครบทุกตัว

รันคำสั่งเดียวเช็คครบ:

```bash
brew --version && weasyprint --version && mutool --version && python3 --version
```

ผลที่ควรเห็น (เวอร์ชันอาจต่างได้):
```
Homebrew 4.x.x
WeasyPrint version 68.x
mutool version 1.27.x
Python 3.13.x
```

> **Python** — macOS รุ่นใหม่มี Python 3 ติดมาในเครื่อง ไม่ต้องลงเพิ่ม (เช็คด้วย `python3 --version`)

---

## 7. เริ่มใช้งานโปรเจกต์

หลังติดตั้งครบ → เปิด UI ของ pipeline:

```bash
cd /path/to/book-dev
./start_ui.sh
```

ครั้งแรก: launcher จะสร้าง Python virtualenv และติดตั้ง Flask + beautifulsoup4 ให้อัตโนมัติ → เปิดเบราว์เซอร์ที่ <http://localhost:5050>

---

## Troubleshooting

### `brew: command not found` หลังติดตั้ง

PATH ยังไม่ active — ปิด Terminal แล้วเปิดใหม่ หรือรัน:
```bash
source ~/.zprofile
```

### `weasyprint: command not found`

ปกติเกิดเพราะ shell ยังไม่เห็น brew → เช็คก่อน `brew list weasyprint`
- ถ้าไม่เจอ → ติดตั้งใหม่ `brew install weasyprint`
- ถ้าเจอแต่เรียกไม่ได้ → ดูว่า PATH มี brew prefix ไหม: `echo $PATH | grep -E "(opt/homebrew|usr/local)"`

### Build ผ่าน UI แล้ว PDF ออกมา **เหมือนกระดาษเปล่า** หรือ **มี error เกี่ยวกับ font**

WeasyPrint หา Pango ไม่เจอ — รัน reinstall:
```bash
brew reinstall weasyprint pango
```

### mutool error: `cannot open ...`

ตรวจว่า input PDF มีอยู่จริง และ path ถูกต้อง  รัน `mutool info <pdf>` ดู metadata ของไฟล์ก่อน

### ICC profile ไม่ตรงกับ output color space

UI จะกรองให้อัตโนมัติ — โปรไฟล์ `(GRAY)` ต้องใช้กับ workflow ขาวดำ, `(CMYK)` กับงาน CMYK เท่านั้น ดูใน dropdown ว่า tag color space ตรงกับงานหรือไม่

### M1/M2 — `bad CPU type in executable`

ติดตั้ง Rosetta 2 (ครั้งเดียว):
```bash
softwareupdate --install-rosetta
```

### อยากถอนทุกอย่าง

```bash
brew uninstall weasyprint mupdf-tools
# ถอน brew เอง (ตัด wipe — ใช้เฉพาะตอนอยากเริ่มใหม่จริงๆ)
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/uninstall.sh)"
```

---

## อ้างอิง

- Homebrew: <https://brew.sh>
- WeasyPrint docs: <https://weasyprint.org>
- MuPDF: <https://mupdf.com>
- pikepdf (Python lib): <https://pikepdf.readthedocs.io>
- ดู workflow build PDF ต่อที่ [STEP.md](STEP.md)
