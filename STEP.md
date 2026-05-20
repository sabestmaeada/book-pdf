# ขั้นตอนสร้าง PDF หนังสือ (ขาวดำ + ฝัง ICC Profile)

คู่มือการ build PDF จาก HTML source ด้วย WeasyPrint + MuPDF (mutool) + pikepdf — **รักษา vector text ตลอด pipeline**

---

## โครงสร้างโฟลเดอร์

```
book-dev/
├── input/                              # HTML source + รูปภาพในเนื้อหา
│   ├── book.html                       # ไฟล์ต้นฉบับ (ห้ามแก้ผ่านสคริปต์)
│   ├── book.synced.html                # สร้างอัตโนมัติจาก sync_toc.py
│   └── images/                         # รูปในเนื้อหาที่ HTML อ้างถึง
├── output/                             # PDF ผลลัพธ์
├── assets/                             # กราฟิกขอบหน้า (edge graphics)
│   ├── left-graphic-18x234mm-300dpi.png
│   └── right-graphic-18x234mm-300dpi.png
├── css/                                # CSS ทั้งหมด
│   ├── weasyprint_print_bw_170x228.css # CSS หลัก (B&W, 170×228mm)
│   ├── edge-graphic-left.css           # CSS วางกราฟิกขอบหน้าคู่ (ซ้าย)
│   ├── edge-graphic-right.css          # CSS วางกราฟิกขอบหน้าคี่ (ขวา)
│   └── no-marks.css                    # CSS ปิด crop marks
├── profiles/                           # ICC profiles
│   └── GrayGamma_2.2.icc               # โปรไฟล์สำหรับ DeviceGray
├── sync_toc.py                         # สคริปต์ sync ชื่อบท → TOC
├── ui/                                 # Flask web UI (วิธีที่ 2)
│   ├── app.py
│   ├── templates/index.html
│   └── static/style.css
├── start_ui.sh                         # ตัวเปิด UI (สร้าง venv + เปิด browser)
├── requirements.txt                    # Python deps สำหรับ UI
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
2. **เลือกขนาดหนังสือ** จาก dropdown
3. **เลือก ICC profile** จาก dropdown (อ่านจาก `profiles/*.icc`)
4. (ไม่บังคับ) อัปโหลด **edge graphic ซ้าย + ขวา** (ต้องครบทั้งคู่ถึงจะใช้)
5. กด **"เริ่มสร้าง PDF"** → log ขึ้นตามเวลาจริง เสร็จแล้วมีลิงก์ดาวน์โหลด

> ต้องติดตั้ง `weasyprint` และ `gs` ในเครื่องไว้ก่อน (ดู Prerequisites ด้านล่าง) — UI เป็นแค่ launcher ไม่ได้ bundle ตัว engine มาด้วย

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
| `book_bw_hq.pdf` | ไฟล์ final ส่งโรงพิมพ์ (DeviceGray + ฝัง ICC) |

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
| รูปในเนื้อหา (`<img src="">`) | HTML (`input/book.synced.html`) | `./images/...` → `input/images/...` |
| Edge graphics (`url()` ใน CSS) | CSS (`css/edge-graphic-{left,right}.css`) | `../assets/...` → `assets/...` |
| ICC profile | คำสั่ง gs (รันจาก root) | `profiles/GrayGamma_2.2.icc` |

ถ้าย้ายโฟลเดอร์ใด ๆ ต้องอัปเดต path ที่อ้างถึงให้สอดคล้อง

---

## Troubleshooting

**Build แล้วรูปขอบหน้าหาย** — เช็กว่า [css/edge-graphic-left.css](css/edge-graphic-left.css) และ [css/edge-graphic-right.css](css/edge-graphic-right.css) อ้าง `../assets/...` (CSS อยู่ใน `css/` ต้องขึ้นไปหนึ่งระดับก่อนเข้า `assets/`)

**Build แล้วรูปในเนื้อหาหาย** — เช็กว่า `<img src="">` ใน HTML ใช้ path สัมพันธ์กับตำแหน่ง HTML (เช่น `./images/foo.jpg` เมื่อ HTML อยู่ใน `input/`)

**สีไม่เป็นขาวดำสนิทหลัง gs** — เช็กว่ามี `-dBlackText=true` และ `-sColorConversionStrategy=Gray` ครบ

**`gs` หา ICC profile ไม่เจอ** — เช็กว่ารันจาก root ของโปรเจกต์ และ path เป็น `profiles/GrayGamma_2.2.icc` (relative กับตำแหน่งที่รันคำสั่ง)

**Build ช้ามาก** — ลบโฟลเดอร์ `.weasy-cache` แล้วลองใหม่ (cache เสีย) หรือใช้ `input/book_test.html` เพื่อทดสอบ layout ก่อน
