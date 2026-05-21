# ขั้นตอนสร้าง PDF หนังสือ (ขาวดำ + ฝัง ICC Profile)

คู่มือการ build PDF จาก HTML source ด้วย WeasyPrint + MuPDF (mutool) + pikepdf — **รักษา vector text ตลอด pipeline**

---

## โครงสร้างโฟลเดอร์

```
book-dev/
├── input/                              # HTML source + รูปภาพในเนื้อหา (gitignored)
│   ├── book.html                       # ไฟล์ต้นฉบับ
│   ├── book.synced.html                # สร้างอัตโนมัติจาก sync_toc.py
│   └── images/                         # รูปในเนื้อหาที่ HTML อ้างถึง
├── output/                             # PDF ผลลัพธ์ (gitignored)
├── assets/                             # กราฟิกขอบหน้า (edge graphics)
│   ├── left-graphic-18x234mm-300dpi.png
│   └── right-graphic-18x234mm-300dpi.png
├── css/                                # CSS ทั้งหมด (auto-detect จากชื่อไฟล์)
│   ├── weasyprint_print_bw_170x228.css # ขนาด 170×228mm
│   ├── weasyprint_print_bw_171x229.css # ขนาด 171×229mm
│   ├── weasyprint_print_bw_190x254.css # ขนาด 190×254mm
│   ├── edge-graphic-left.css           # กราฟิกขอบหน้าซ้าย (optional)
│   ├── edge-graphic-right.css          # กราฟิกขอบหน้าขวา (optional)
│   └── no-marks.css                    # ปิด crop marks (default)
├── profiles/                           # ICC profiles (auto-detect color space)
│   ├── GrayGamma_2.2.icc               # GRAY
│   ├── Dot Gain 15%.icc                # GRAY
│   └── UncoatedFOGRA29.icc             # CMYK
├── ui/                                 # Flask web UI
│   ├── app.py
│   ├── templates/index.html
│   └── static/style.css
├── sync_toc.py                         # sync ชื่อบทใน TOC → ตาม <h1 class="ch-title">
├── check_icc.py                        # ตรวจ ICC profile ที่ฝังใน PDF
├── start_ui.sh                         # launcher UI (สร้าง venv + เปิด browser)
├── requirements.txt                    # Python deps (flask, beautifulsoup4, pikepdf)
├── .gitignore
├── INSTALL.md                          # คู่มือติดตั้ง Homebrew/WeasyPrint/MuPDF
└── STEP.md                             # ไฟล์นี้
```

---

## ⚡ วิธีที่ง่ายที่สุด — เปิด Web UI

```bash
./start_ui.sh
```

ครั้งแรก: สคริปต์จะสร้าง virtualenv และติดตั้ง dependencies ให้อัตโนมัติ → เปิดเบราว์เซอร์ที่ <http://localhost:5050>

ใน UI:
1. **อัปโหลด ZIP** ที่มี HTML และรูปประกอบ (จะถูกแตกลง `input/` — ของเดิมในนั้นจะถูกลบ)
2. **เลือกขนาดหนังสือ** จาก dropdown (auto-detect จาก `css/weasyprint_print_*.css`)
3. **เลือก ICC profile** จาก dropdown (auto-detect color space จาก ICC header → match กับ mutool/pikepdf อัตโนมัติ)
4. ☐ ติ๊ก **"แสดง crop marks"** ถ้าต้องการขอบตัดในไฟล์ (default ปิดไว้)
5. (ไม่บังคับ) อัปโหลด **edge graphic ซ้าย หรือ ขวา** อย่างใดอย่างหนึ่งหรือทั้งคู่ก็ได้
6. กด **"เริ่มสร้าง PDF"** → log ขึ้นตามเวลาจริง เสร็จแล้วมีลิงก์ดาวน์โหลด

> ต้องติดตั้ง `weasyprint` และ `mutool` ในเครื่องไว้ก่อน (ดู [INSTALL.md](INSTALL.md)) — UI เป็นแค่ launcher ไม่ได้ bundle engine มาด้วย

---

## ข้อกำหนดเบื้องต้น (Prerequisites)

ติดตั้งครั้งเดียวก่อนใช้งาน:

```bash
# WeasyPrint + MuPDF (macOS)
brew install weasyprint mupdf-tools

# Python libs (สำหรับ UI + sync_toc + ICC embed)
pip install beautifulsoup4 pikepdf flask
```

ตรวจสอบเวอร์ชัน:

```bash
weasyprint --version    # ทดสอบกับ 68.1
mutool --version        # ทดสอบกับ 1.27
python3 --version       # ต้องเป็น 3.9 ขึ้นไป
```

ดูคู่มือติดตั้งเต็มได้ที่ [INSTALL.md](INSTALL.md)

---

## วิธีที่ 2 — สั่งจาก command line (3 ขั้นตอน)

สำหรับคนที่ต้องการ scripting/automation รันคำสั่งจาก root ของโปรเจกต์ (`book-dev/`)

### Step 1 — Sync ชื่อบทใน TOC

อ่าน `<h1 class="ch-title">` ในแต่ละบท แล้วเขียนทับ `<span class="toc-name">` ใน TOC ให้ตรงกัน

```bash
python3 sync_toc.py input/book.html -o input/book.synced.html
```

ผลลัพธ์: ไฟล์ใหม่ `input/book.synced.html` (ไฟล์ต้นฉบับ `book.html` ไม่ถูกแตะ)
สคริปต์จะรายงานจำนวน entry ที่อัปเดตและเตือนถ้ามี TOC entry ที่หา chapter ไม่เจอ

### Step 2 — สร้าง PDF ด้วย WeasyPrint

```bash
weasyprint \
  -s css/weasyprint_print_bw_170x228.css \
  -s css/edge-graphic-left.css \
  -s css/edge-graphic-right.css \
  -s css/no-marks.css \
  --pdf-variant pdf/x-4 \
  --optimize-images -j 90 -D 300 \
  -c .weasy-cache \
  input/book.synced.html \
  output/book_rgb_bw_nomarks.pdf
```

อธิบาย flag:
- `-s <file>` — โหลด stylesheet เพิ่ม (เรียงตามลำดับ override)
- `--pdf-variant pdf/x-4` — เอาต์พุตตามมาตรฐาน PDF/X-4
- `--optimize-images -j 90` — บีบ JPEG คุณภาพ 90
- `-D 300` — DPI 300 สำหรับงานพิมพ์
- `-c .weasy-cache` — ใช้ cache เพื่อ build ครั้งถัดไปเร็วขึ้น

### Step 3 — แปลง color space + ฝัง ICC (mutool + pikepdf)

**3a) แปลง color space ด้วย mutool** (preserve vector text)

```bash
mutool recolor -c gray -o output/book_gray_interim.pdf output/book_rgb_bw_nomarks.pdf
```

`-c` รองรับ `gray`, `rgb`, `cmyk` — เลือกให้ตรงกับ ICC profile ที่จะใช้

**3b) ฝัง ICC profile ด้วย pikepdf** (Python)

```bash
python3 -c "
import pikepdf
with pikepdf.open('output/book_gray_interim.pdf') as pdf:
    with open('profiles/GrayGamma_2.2.icc', 'rb') as f:
        icc = f.read()
    stream = pdf.make_stream(icc, {'/N': 1})   # /N: 1=Gray, 3=RGB, 4=CMYK
    intent = pikepdf.Dictionary({
        '/Type': pikepdf.Name('/OutputIntent'),
        '/S': pikepdf.Name('/GTS_PDFX'),
        '/OutputCondition': pikepdf.String('GrayGamma 2.2'),
        '/OutputConditionIdentifier': pikepdf.String('Custom'),
        '/Info': pikepdf.String('Gray color space'),
        '/DestOutputProfile': stream,
    })
    pdf.Root['/OutputIntents'] = pikepdf.Array([intent])
    pdf.save('output/book_gray_hq.pdf')
"
rm output/book_gray_interim.pdf
```

**ทำไมไม่ใช้ Ghostscript (`gs`)**
- gs มักจะ **rasterize PDF** ที่มี CID Thai/CJK fonts ตอนแปลง color space → text กลายเป็นภาพ
- pipeline ใหม่ (mutool + pikepdf) เร็วกว่าประมาณ 30 เท่า (~1s vs ~30s) และไฟล์เล็กลงประมาณครึ่งหนึ่ง

---

## สั่งรวดเดียวทั้ง 3 ขั้น

```bash
python3 sync_toc.py input/book.html -o input/book.synced.html && \
weasyprint -s css/weasyprint_print_bw_170x228.css \
  -s css/edge-graphic-left.css -s css/edge-graphic-right.css \
  -s css/no-marks.css \
  --pdf-variant pdf/x-4 --optimize-images -j 90 -D 300 -c .weasy-cache \
  input/book.synced.html output/book_rgb_bw_nomarks.pdf && \
mutool recolor -c gray -o output/_interim.pdf output/book_rgb_bw_nomarks.pdf && \
python3 -c "
import pikepdf
with pikepdf.open('output/_interim.pdf') as pdf:
    with open('profiles/GrayGamma_2.2.icc', 'rb') as f: icc = f.read()
    stream = pdf.make_stream(icc, {'/N': 1})
    intent = pikepdf.Dictionary({
        '/Type': pikepdf.Name('/OutputIntent'), '/S': pikepdf.Name('/GTS_PDFX'),
        '/OutputCondition': pikepdf.String('GrayGamma 2.2'),
        '/OutputConditionIdentifier': pikepdf.String('Custom'),
        '/Info': pikepdf.String('Gray color space'),
        '/DestOutputProfile': stream,
    })
    pdf.Root['/OutputIntents'] = pikepdf.Array([intent])
    pdf.save('output/book_gray_hq.pdf')
" && rm output/_interim.pdf
```

---

## ตรวจสอบ ICC profile ใน PDF

ใช้ [check_icc.py](check_icc.py) ดูว่า PDF ฝังโปรไฟล์สีอะไร / ตรงกับไฟล์ใน `profiles/` ตัวไหน

```bash
python3 check_icc.py output/book_gray_hq.pdf
```

หลายไฟล์พร้อมกันก็ได้:
```bash
python3 check_icc.py output/*.pdf
python3 check_icc.py output/book_gray_hq.pdf /tmp/another.pdf
```

ตัวอย่างผลลัพธ์:
```
📄 output/book_gray_hq.pdf
   ขนาด: 2473.0 KB

   OutputIntent[0]:
      Subtype       : /GTS_PDFX
      Condition     : GrayGamma_2.2.icc
      Identifier    : Custom
      Info          : Gray color space
      ICC channels  : /N = 1
      ICC color sp. : GRAY (1-channel grayscale)
      ICC data size : 4,456 bytes
      ICC MD5       : 8c1b15ed8e3fd5d0...
      ✅ ตรงกับ      : profiles/GrayGamma_2.2.icc
```

สคริปต์เปลี่ยนไปใช้ `.venv/bin/python3` ของโปรเจกต์เองอัตโนมัติ → ไม่ต้องระบุ `.venv` เอง

**ถ้าเจอ `PermissionError` ตอนเปิดไฟล์จาก `~/Downloads`**

macOS ป้องกัน `~/Downloads`, `~/Documents`, `~/Desktop` ไม่ให้ terminal เข้าถึงโดยไม่อนุญาต ทางแก้:

| วิธี | คำสั่ง |
|---|---|
| ก็อปไปที่ `/tmp/` ก่อน | `cp ~/Downloads/foo.pdf /tmp/ && python3 check_icc.py /tmp/foo.pdf` |
| ย้ายเข้าโปรเจกต์ | `mv ~/Downloads/foo.pdf output/ && python3 check_icc.py output/foo.pdf` |
| ให้สิทธิ์ถาวร | System Settings → Privacy & Security → **Files and Folders** → Terminal → เปิด **Downloads Folder** (ปิด Terminal เปิดใหม่) |

---

## ไฟล์ผลลัพธ์

หลังรันครบ 3 ขั้น จะได้ 2 ไฟล์ใน `output/`:

| ไฟล์ | สำหรับ |
|---|---|
| `book_rgb_bw_nomarks.pdf` | ไฟล์กลาง (RGB, PDF/X-4) — ใช้ตรวจเลย์เอาต์ |
| `book_<colorspace>_hq.pdf` | ไฟล์ final ส่งโรงพิมพ์ — vector text + ฝัง ICC |

ชื่อ `<colorspace>` ตามที่ pipeline ตัดสินจาก ICC ที่เลือก:
- `book_gray_hq.pdf` — เมื่อ ICC เป็น GRAY (GrayGamma 2.2, Dot Gain 15%)
- `book_cmyk_hq.pdf` — เมื่อ ICC เป็น CMYK (UncoatedFOGRA29)
- `book_rgb_hq.pdf` — เมื่อ ICC เป็น RGB

---

## เปิด/ปิด crop marks

ปกติคำสั่งด้านบนใช้ `css/no-marks.css` ซึ่ง **ปิด** crop marks

ถ้าต้องการ crop marks (สำหรับโรงพิมพ์) ให้ลบ `-s css/no-marks.css` ออก:

```bash
weasyprint -s css/weasyprint_print_bw_170x228.css \
  -s css/edge-graphic-left.css -s css/edge-graphic-right.css \
  --pdf-variant pdf/x-4 --optimize-images -j 90 -D 300 -c .weasy-cache \
  input/book.synced.html output/book_rgb_bw_marks.pdf
```

---

## การแก้ไขชื่อบท

1. แก้ใน `<h1 class="ch-title">` ของบทที่ต้องการ ใน `input/book.html` (source of truth)
2. รัน Step 1 อีกครั้ง — TOC จะอัปเดตให้อัตโนมัติ
3. รัน Step 2 และ 3 ตามปกติ

ไม่ต้องไปแก้ `<span class="toc-name">` ในส่วน TOC เอง — สคริปต์จัดการให้

---

## Path resolution (สำคัญเมื่อย้ายไฟล์)

WeasyPrint resolve path ของ resource ตาม **ตำแหน่งของไฟล์ที่อ้างถึง** ไม่ใช่ตามที่รันคำสั่ง:

| Resource | อ้างจากไหน | Path ที่ใช้ |
|---|---|---|
| รูปในเนื้อหา (`<img src="">`) | HTML (`input/.../book.html`) | `./images/...` → resolve relative to HTML |
| Edge graphics (`url()` ใน CSS) | CSS (`css/edge-graphic-{left,right}.css`) | `../assets/...` → `assets/...` |
| ICC profile | Python pikepdf (รันจาก root) | `profiles/GrayGamma_2.2.icc` |

ถ้าย้ายโฟลเดอร์ใด ๆ ต้องอัปเดต path ที่อ้างถึงให้สอดคล้อง

---

## Troubleshooting

**Build แล้วรูปขอบหน้าหาย** — เช็กว่า [css/edge-graphic-left.css](css/edge-graphic-left.css) และ [css/edge-graphic-right.css](css/edge-graphic-right.css) อ้าง `../assets/...` (CSS อยู่ใน `css/` ต้องขึ้นไปหนึ่งระดับก่อนเข้า `assets/`)

**Build แล้วรูปในเนื้อหาหาย** — เช็กว่า `<img src="">` ใน HTML ใช้ path สัมพันธ์กับตำแหน่ง HTML (เช่น `./images/foo.jpg` เมื่อ HTML อยู่ใน `input/`)

**PDF เป็นแถบเส้นแนวตั้ง / ขอบเพี้ยน** — มักเกิดจาก CSS หลักกับ asset ขนาดไม่ match (เช่น cover image 176×234 ใส่ในเล่ม 190×254 → เหลือช่องว่าง) เช็กว่า `width/height` ของ cover image ใน CSS = trim + 6mm bleed

**`mutool` หา input ไม่เจอ** — รัน `mutool info <pdf>` ตรวจไฟล์ก่อน หรือดูว่า path ที่ส่งเข้า script ตรงกับไฟล์จริงไหม

**ICC profile ไม่ match กับ output color space** — UI กรองให้แล้วผ่าน color space ของ ICC (GRAY/CMYK/RGB) ที่อ่านจาก header ของไฟล์ ICC; ถ้ายังพัง ใช้ [check_icc.py](check_icc.py) เทียบกับผลลัพธ์

**Build ช้ามาก / PDF ออกมาผิดเพี้ยน (รูปเก่า, layout แปลก)** — `.weasy-cache/` อาจเสีย

- ใน Web UI กดปุ่ม **"ล้าง cache"** ข้างปุ่ม "เริ่มสร้าง PDF"
- หรือลบเองจาก terminal:
  ```bash
  cd /path/to/book-dev
  rm -rf .weasy-cache
  ```

**`./start_ui.sh` แล้วเจอ `No module named 'pikepdf'` (หรือ Flask / bs4)**

มักเกิดเมื่อ **copy โฟลเดอร์โปรเจกต์ไปอีกเครื่อง** แล้ว `.venv/` ถูก copy ไปด้วย — virtualenv ของ Python **ย้ายเครื่องไม่ได้** (symlink ภายในชี้ไป Python ของเครื่องเดิม)

แก้:
```bash
cd /path/to/book-dev
rm -rf .venv
./start_ui.sh
```

`start_ui.sh` จะสร้าง venv ใหม่ + ลง dependencies (Flask, beautifulsoup4, pikepdf) ให้อัตโนมัติ ใช้เวลาประมาณ 30 วินาที – 1 นาที

> **เวลา copy โปรเจกต์ข้ามเครื่อง** — exclude `.venv/`, `.weasy-cache/`, `__pycache__/`, `input/`, `output/` ออกก่อน (หรือใช้ git clone แทน copy ทั้งโฟลเดอร์)

**หน้าใน PDF กลายเป็นภาพ raster (text search ไม่ได้)** — ใช้ pipeline เก่าที่ใช้ `gs`; pipeline ปัจจุบัน (mutool + pikepdf) ต้องให้ text เป็น vector — ใช้ [check_icc.py](check_icc.py) + ดูจำนวนหน้าที่ extract text ได้
