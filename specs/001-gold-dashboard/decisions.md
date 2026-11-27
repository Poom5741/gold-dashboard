# Gold Dashboard — Verified Decisions & Environment Facts (27 พ.ย. 2026)

Worker ต้องอ่านไฟล์นี้ก่อนวางแผน — คือข้อสรุปจากการตรวจสอบจริงแล้วทั้งหมด ห้ามทำซ้ำหรือตัดสินใจใหม่ในข้อที่ปิดแล้ว

## การตัดสินใจที่ Poom ยืนยันแล้ว
1. **CME browser collector** สร้างเลย — ใช้ free CME account ของ Poom, รันบน GitHub Actions (แบบ Gold-Sight: CME_EMAIL/CME_PASSWORD เป็น repo secrets) — ประเด็น ToU ของ CME เป็นความยอมรับความเสี่ยงของ Poom เอง
2. ทุกอย่างอื่นใน RESEARCH.md ผ่านการยอมรับแล้ว

## ผลตรวจแล้ว (อย่าทำซ้ำ)
- โครงสร้างโปรเจกต์: `/root/workspace/gold-dash/` (SPEC.md, RESEARCH.md, research/ = clones 3 repos ไว้อ่านอ้างอิง)
- Yahoo (GC=F, DX-Y.NYB) ✅ · FRED CSV ไม่ต้องใช้ key ✅ · CFTC API ✅ (field `cftc_contract_market_code=088691`)
- TVdataOptionOI: MIT ✅, ดึง chain GC1! ได้ (IV/delta จริง) แต่ **OI = None ทุก contract** — ใช้เพื่อ IV/25ΔRR/expected range เท่านั้น
- CME CmeWS จาก VPS: **403 IP-blocked + ToU ห้าม scraping** — ห้าม scrape ตรงจาก server; collector CME ต้องเป็น browser automation บน GitHub Actions runner เท่านั้น
- Gold-Sight-by-OI กับ xau-oi-lab: **ไม่มี license** — อ่านเป็นแนวทางได้ (CME SSO flow: login.cmegroup.com, Vol2Vol URL `cmegroup.com/tools-information/quikstrike/vol2vol-expected-range.html`, dedupe expiry+strike) **ห้าม copy โค้ด**

## สถาปัตยกรรมที่สอดคล้องกับการตัดสินใจ
```
GitHub Actions (Poom's repo)          VPS (Hermes host, 8GB, docker มี)
└─ cme-collector (Playwright)         └─ docker-compose:
   ├─ CME login (secrets)                ├─ backend: FastAPI + APScheduler
   ├─ Vol2Vol tenor + OI chain           │   ├─ collectors: yahoo/fred/cftc/tvdataoption (in-process)
   └─ commit JSON snapshot → data repo   │   ├─ bias engine (weights จาก config)
                                         │   └─ SQLite persistence
                                         └─ frontend: Nuxt 3 + LightweightCharts + ECharts
สายข้อมูล: backend pull JSON จาก data repo (deploy key / raw URL) ทุก schedule
```
- Data flow จาก Actions → data repo (แนะนำ repo แยก private `poom-gold-data` หรือ branch data/ ใน repo เดียวกัน — worker เลือกได้แต่ต้อง deploy key ได้)
- Poom ต้องเพิ่ม secrets เองภายหลัง: CME_EMAIL, CME_PASSWORD (worker ห้ามขอ/ไม่ต้องใช้จริงเพื่อทดสอบ — ทำ dry-run mode + mock fixtures แทน)

## ข้อจำกัดสภาพแวดล้อม
- VPS 8GB แชร์กับ fleet อื่น (rakazo containers, pgdata ห้ามแตะ) — ห้ามใช้ RAM/แตะ service คนอื่น
- python3 บนเครื่องมี yfinance/tvdataoption ติดตั้งแล้ว (ทดสอบแล้ว) แต่ production ต้อง lock ใน Docker image
- git push token: อ่านจาก /root/.config/gh/hosts.yml (ผ่าน python re แล้วใช้ x-access-token:<token>@github.com — ห้าม print token)
