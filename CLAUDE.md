# CLAUDE.md

บริบทโปรเจกต์สำหรับ Claude อ่านทุกครั้งที่เข้ามาทำงาน

---

## โปรเจกต์นี้คืออะไร

Pipeline สร้าง PDF หนังสือคุณภาพสำหรับโรงพิมพ์ + Flask UI ภาษาไทย
- Input: HTML (พร้อมรูปภาพ) ที่ออกแบบเป็นเล่มหนังสือ
- Output: PDF/X-4 vector ฝัง ICC profile พร้อมส่งโรงพิมพ์
- User: ผู้เขียนหนังสือ (sole developer) — สื่อสารด้วยภาษาไทย

## Pipeline ปัจจุบัน

```
HTML → [sync_toc.py] → HTML (TOC ถูกต้อง)
     → [WeasyPrint]   → RGB PDF/X-4 (vector)
     → [mutool recolor] → grayscale/CMYK PDF (vector, preserve text)
     → [pikepdf]      → ฝัง ICC profile ลง /OutputIntents
```

**⚠️ ห้ามใช้ Ghostscript (`gs`)** — gs จะ rasterize PDF ที่มี CID Thai fonts (text กลายเป็น bitmap, search ไม่ได้, ไฟล์ใหญ่ขึ้น 8 เท่า) เราเลิกใช้แล้วและไม่ควรกลับไปใช้

## ไฟล์สำคัญ

| ไฟล์ | บทบาท |
|---|---|
| [ui/app.py](ui/app.py) | Flask backend — ทุก logic อยู่ในนี้ |
| [sync_toc.py](sync_toc.py) | sync ชื่อบทใน TOC จาก `<h1 class="ch-title">` |
| [check_icc.py](check_icc.py) | ตรวจ ICC profile ใน PDF (auto-bootstrap venv) |
| [start_ui.sh](start_ui.sh) | launcher — สร้าง venv, ติดตั้ง deps, เปิด browser |
| [STEP.md](STEP.md) / [INSTALL.md](INSTALL.md) | คู่มือ user (ไม่ต้องไปแก้ตอนทำงาน feature) |

## Convention สำคัญ

### ขนาดหนังสือ — auto-detect จากชื่อ CSS
Pattern: `css/weasyprint_print_<variant>_<W>x<H>.css`
- variant: `bw`/`mono` = default (ไม่มี label), `color` = "(สี)", `cmyk` = "(CMYK)"
- เพิ่มขนาด → copy file + sed แทน 4 ค่า: `170mm`→W, `228mm`→H, `176mm`→W+6, `234mm`→H+6
- (W+6 / H+6 = trim + bleed 3mm × 2 ใช้ใน `.cover-image`)

### ICC profile — auto-detect จาก ICC header
- อ่าน bytes 16..19 ของไฟล์ ICC → `'GRAY'`/`'CMYK'`/`'RGB '`
- map ไปยัง mutool arg + /N channel → `_ICC_CS_TABLE` ใน `ui/app.py`
- pikepdf ฝัง ICC ลง `/OutputIntents` พร้อม proper PDF/X dictionary

### Edge graphics — ซ้าย/ขวาแยกอิสระ
- `css/edge-graphic-left.css` และ `css/edge-graphic-right.css`
- Backend include เฉพาะที่ user upload (อย่างใดก็ได้)

### Crop marks — checkbox UI
- ถ้าติ๊ก → ไม่ include `no-marks.css` → @page rule ใน CSS หลัก (`marks: crop`) ทำงาน
- ถ้าไม่ติ๊ก (default) → include `no-marks.css` → override เป็น `marks: none`

## Path resolution (สำคัญตอนทำ feature ที่เกี่ยวกับไฟล์)

WeasyPrint resolve relative path ตาม **ตำแหน่งของไฟล์ที่อ้างถึง** ไม่ใช่ cwd:
- รูปในเนื้อหา `<img src="./images/x.jpg">` → resolve relative to HTML location
- Edge graphics `url("../assets/x.png")` → relative to CSS file (`css/` → `../assets/`)
- ICC profile → relative to cwd ของ Python process (root ของโปรเจกต์)

**อย่าลืม:** `synced_html = html_path.with_name(...)` (ไม่ใช่ `INPUT_DIR / "..."`) เพื่อให้ relative path ใน HTML ยัง resolve ถูก

## Gotchas / สิ่งที่เคยพลาด

1. **`clear_dir()` เคยลบ `.gitkeep`** — fix แล้ว: skip files ขึ้นต้นด้วย `.`
2. **macOS ZIP มี junk** (`__MACOSX/`, `._foo`, `.DS_Store`) — กรองใน `_is_macos_junk()`
3. **`176mm`/`234mm` ใน CSS = trim + bleed** ไม่ใช่ trim — sed แทนค่าต้องครอบคลุมด้วย
4. **`.weasy-cache/` cache เสีย** อาจทำให้ build ผลแปลก — ลบทิ้งแล้วลองใหม่
5. **Browser cache** อาจถือ HTML เก่าที่มี dropdown key เก่า — hard refresh (Cmd+Shift+R) หลังเปลี่ยน schema
6. **macOS TCC** ป้องกัน `~/Downloads`, `~/Documents`, `~/Desktop` จาก terminal — script `check_icc.py` ใช้ไฟล์ใน path เหล่านี้จะ error PermissionError

## พฤติกรรมที่ user ต้องการ

- **ภาษาไทย**: สื่อสาร 100% ภาษาไทย, commit message ก็ภาษาไทย
- **ตอบกระชับ**: ไม่ต้องอธิบายยาว, focus result
- **ห้ามอ่าน .env/secrets** โดยไม่ขออนุญาต (ดู `~/.claude/CLAUDE.md` ของ user)
- **อย่า commit เอง** — รอ user สั่ง
- **ห้ามใช้ emoji เกินจำเป็น** — ถ้าไม่ขอ ใช้ ✓/✗ หรือ markdown แทน

## คำสั่งที่ใช้บ่อย

```bash
# เริ่ม UI
./start_ui.sh                              # port 5050

# สร้าง PDF จาก command line (3 ขั้นรวด — ดู STEP.md)
python3 sync_toc.py input/book.html -o input/book.synced.html
weasyprint -s css/weasyprint_print_bw_170x228.css ... input/book.synced.html output/book_rgb_bw_nomarks.pdf
mutool recolor -c gray -o /tmp/_x.pdf output/book_rgb_bw_nomarks.pdf
python3 -c "import pikepdf; ..."           # embed ICC (ดู STEP.md Step 3b)

# ตรวจ ICC + ขนาด/text/raster ใน PDF
python3 check_icc.py output/book_gray_hq.pdf

# kill server เก่า + ลบ cache ก่อน restart
lsof -ti :5050 | xargs kill 2>/dev/null; rm -rf .weasy-cache
```

## โครงสร้าง code ที่ควรรู้

`ui/app.py` แบ่งเป็น:
1. **Helpers**: `_icc_colorspace`, `list_book_sizes`, `list_profiles`, `safe_extract_zip`, `find_html`, `clear_dir`
2. **Pipeline**: `stream_subprocess`, `apply_color_pipeline`, `build_pipeline` (thread)
3. **Routes**: `/`, `/build` (streaming response), `/download/<name>`

ทุก route ใช้ `list_*()` functions ที่ scan ดิสก์ใหม่ทุกครั้ง → user เพิ่มไฟล์ใน `css/`, `profiles/`, `assets/` แล้ว refresh หน้าเว็บ → เห็นทันที (ไม่ต้อง restart)
