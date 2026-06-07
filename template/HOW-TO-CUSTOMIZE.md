# 🎨 วิธีปรับสไตล์หนังสือของคุณ

> เขียนสำหรับ **ผู้ที่ไม่มีความรู้ CSS** — ทำตามได้เป็นขั้นๆ

---

## 4 ทางเลือก เริ่มจากง่ายที่สุด

| ทางเลือก | เหมาะกับ | เวลา |
|---|---|---|
| 1️⃣ **ใช้ EXAMPLE ตรงๆ** | สไตล์มาตรฐานที่มีอยู่ตรงใจ | 1 นาที |
| 2️⃣ **EXAMPLE + แก้สีนิดเดียว** | อยากเปลี่ยนแค่สี/ฟอนต์ | 5 นาที |
| 3️⃣ **ใช้ BRIEF-FORM + AI** | อยากได้ของใหม่ทั้งหมด ไม่ต้องเขียน CSS | 15 นาที |
| 4️⃣ **แก้ template-print.gemini.css เอง** | มี knowledge CSS บางส่วน | 30+ นาที |

---

## 1️⃣ ใช้ EXAMPLE ตรงๆ (ง่ายที่สุด)

ดูใน `template/EXAMPLES/` มีสไตล์พร้อมใช้:

| ไฟล์ | มู้ด | สี | ฟอนต์ |
|---|---|---|---|
| `template-print.gemini.css` | โมเดิร์น-มินิมัล | น้ำเงิน Google | Poppins / Anuphan |
| `EXAMPLES/example_classic.css` | คลาสสิก-ทางการ | แดงเบอร์กันดี | Sarabun |
| `EXAMPLES/example_workbook.css` | วิชาการ-textbook | เขียวมิ้นต์ | Mitr / Anuphan |
| `EXAMPLES/example_minimal.css` | มินิมัล B&W | ดำ-เทา | IBM Plex Sans Thai |

**วิธีใช้:**
1. เปิด UI → ช่อง "Template CSS ส่วนตัว"
2. กดเลือกไฟล์ → เลือกไฟล์ที่ต้องการ
3. กด "สร้าง PDF"

✓ จบ ไม่ต้องแก้อะไร

---

## 2️⃣ EXAMPLE + แก้สีนิดเดียว

ถ้าชอบสไตล์ใน EXAMPLE แต่อยากเปลี่ยนสีหรือฟอนต์

**ขั้นตอน:**
1. Copy ไฟล์ EXAMPLE ตั้งชื่อใหม่ เช่น `my_book.css`
2. เปิดด้วย text editor (Notes, TextEdit, VS Code อะไรก็ได้)
3. ดูที่ **section 2 (Variables)** — แก้ค่าใน `:root { ... }`

### ตัวอย่างแก้สี

ใน `EXAMPLES/example_classic.css` ค้นหา:

```css
--tpl-accent:    #8B1538 !important;   /* Burgundy */
--tpl-accent-dk: #5E0E25 !important;
--tpl-accent-lt: #FAEEF1 !important;
```

อยากเปลี่ยนเป็นน้ำเงินทางการ → เปลี่ยนเป็น:

```css
--tpl-accent:    #1F3A93 !important;   /* น้ำเงินทางการ */
--tpl-accent-dk: #0F2255 !important;
--tpl-accent-lt: #EEF3FA !important;
```

ทั้งเล่มเปลี่ยนทันที — เพราะทุกที่อ้างอิงผ่าน variable

### ตัวอย่างแก้ฟอนต์

ค้นหาบรรทัด `@import` (Section 1) — เปลี่ยนชื่อฟอนต์จาก Google Fonts

ค้นหา `--tpl-hd` `--tpl-bd` ใน Section 2 — เปลี่ยนชื่อฟอนต์

---

## 3️⃣ ใช้ BRIEF-FORM + AI (แนะนำสำหรับคนทั่วไป)

ถ้าอยากได้สไตล์ใหม่ที่ไม่เคยมี ใช้วิธีนี้

**ขั้นตอน:**

### Step 1 — เปิดไฟล์ form
เปิด `template/BRIEF-FORM.md` ด้วย text editor หรือ markdown viewer

### Step 2 — ติ๊กตอบ
- มี 7 คำถามหลัก + Q8 optional
- เปลี่ยน `[ ]` → `[x]` ในข้อที่ต้องการ
- กรอกข้อความตรง `อื่นๆ:` ถ้ามี
- ลบช้อยส์ที่ไม่เลือกได้ (หรือเก็บไว้ก็ได้)

### Step 3 — copy ทั้งฟอร์ม
- Cmd+A → Cmd+C ทั้งไฟล์ (หรือเฉพาะส่วน "ส่งให้ AI" ลงไป)

### Step 4 — paste ใน AI
- เปิด ChatGPT / Claude / Gemini
- paste form ที่ตอบแล้ว
- ส่ง

### Step 5 — รับ CSS
- AI จะส่ง CSS เต็มไฟล์กลับมา
- copy โค้ด CSS ที่ได้ → save เป็น `.css` (เช่น `my_template.css`)

### Step 6 — upload ใช้งาน
- เปิด UI → ช่อง "Template CSS ส่วนตัว"
- เลือกไฟล์ที่เพิ่ง save
- กด "สร้าง PDF"

### Step 7 — iterate
- เห็น PDF แล้วไม่ถูกใจตรงไหน → ส่งให้ AI แก้
- "หัวบทเล็กไป" / "สีอ่อนไป" / "เพิ่มกล่องโน้ตหลายแบบ"
- รับ CSS รุ่นใหม่ → upload ใหม่

---

## 4️⃣ แก้ template-print.gemini.css เอง

ถ้ามี knowledge CSS อยู่บ้าง — เปิด `template/template-print.gemini.css` แล้วแก้ section ที่ต้องการโดยตรง

ไฟล์มี 17 sections พร้อม comment อธิบายแต่ละจุด

---

## ⚠ ข้อควรระวัง

### ที่ห้ามแตะใน custom CSS ของคุณ
- `@page { size, margin, bleed, marks }` — กำหนดใน sizes/ แล้ว
- `.cover-image { width, height }` — ขนาดปก
- `.credits-page { min-height }` — fit 1 หน้า
- `.bd-row` / `.bd-col` ที่มี `display: table` — ระบบ grid
- `counter-reset` ของ `.content ol` — Thai counter mode
- `@counter-style thai-alpha` — ก, ข, ค markers
- `string-set: chapter-title` — running header บนหน้าซ้าย

### WeasyPrint ไม่รองรับ
ถ้าเห็น warning เหล่านี้ใน build log — ไม่ใช่ bug แต่ feature ที่ใส่ไปจะถูก ignore:
- `box-shadow`, `text-shadow`
- `print-color-adjust`
- `width: fit-content`
- gradient text (เช่น `background-clip: text`)
- transform หลายแบบ

### ฟอนต์
- ทุก font-family ต้องมี **Thai fallback** เสมอ
- ตัวอย่าง: `'Poppins', 'IBM Plex Sans Thai', sans-serif`
- ถ้าใช้ Google Fonts → ต้อง `@import` ก่อน

---

## ❓ ถ้าผลลัพธ์ผิดไปจากที่ต้องการ

### "สีไม่เปลี่ยน"
- ลืม `!important` ที่ท้ายค่า → ต้องใส่ทุกบรรทัด

### "PDF เพี้ยน หน้าหาย กลายเป็นว่าง"
- ลบ template CSS file ที่ใช้ → build ใหม่
- หรือใช้ EXAMPLE เดิมก่อน → debug ทีหลัง

### "ฟอนต์ไทยกลายเป็นกล่อง"
- ลืมใส่ Thai fallback ใน font-family
- หรือชื่อฟอนต์ใน @import ผิด

### "Warning ใน build log"
- ดูที่ section "WeasyPrint ไม่รองรับ" ด้านบน
- ถ้ามี `width: fit-content` → เปลี่ยนเป็น `display: block` + ::after underline

### อยากได้ feature ใหม่ที่ EXAMPLE ไม่มี
- ใช้ BRIEF-FORM + AI (วิธีที่ 3)
- หรือถามใน chat: "อยากได้ feature X ใน custom_template — เพิ่มยังไง"

---

## 📚 อ้างอิงโครงสร้าง CSS

ทุก template CSS มี 17 sections โครงสร้างเดียวกัน:

```
1.  Fonts (@import)
2.  Variables (--tpl-*)
3.  Body (html, body, .content p, ul, ol, li)
4.  Headings (h1, h2, h3, h4)
5.  Heading → p spacing
6.  Chapter header (.ch-hdr, .ch-num, .ch-title)
7.  Inline elements (strong, em, mark)
8.  OL counter
9.  Quiz reset
10. Drop cap
11. Code blocks
12. Note
13. Blockquote
14. Tables
15. TOC
16. Preface
17. Image markers + figure + hr
```

ถ้าอยากแก้แค่อันเดียว → ค้น section นั้น → แก้ → save → upload

---

## 🎯 Quick Reference

| ต้องการ | แก้ที่ |
|---|---|
| เปลี่ยนสี theme | Section 2 — `--tpl-accent*` |
| เปลี่ยนฟอนต์ | Section 1 (@import) + Section 2 (`--tpl-hd/bd/cd`) |
| ปรับขนาด heading | Section 4 |
| ปรับขนาด body | Section 3 — `.content p { font-size }` |
| เปลี่ยนสีและสไตล์ note | Section 12 |
| เปลี่ยนสไตล์ code block | Section 11 |
| เอา drop cap ออก | Section 10 — set font-size: inherit, float: none |
| เปลี่ยนสไตล์ OL marker | Section 8 |

---

## 🆘 ติดปัญหา

ถ้าทำตามนี้แล้วยังไม่ได้ ลอง:
1. ใช้ EXAMPLE ใกล้เคียงที่สุด → build ดูก่อน
2. แก้ทีละ section → build ดูทีละครั้ง
3. ถามใน chat กับ Claude — แนบไฟล์ template ที่กำลังแก้
