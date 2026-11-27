# Gold Dashboard MVP — Data Source Research (27 พ.ย. 2026)

สรุปผลตรวจสอบก่อนเริ่ม implement (ตาม spec ข้อ 3: ตรวจ repos ก่อนเขียน collector ใหม่)

## Repos ที่กำหนดให้ตรวจ

| Repo | สถานะ | License | ใช้อะไรได้ |
|---|---|---|---|
| Hewkaw02/Gold-Sight-by-OI | live (6bab5de) | ❌ ไม่มี license file | เอาได้แค่ "แนวทาง": CME SSO login flow (login.cmegroup.com), Vol2Vol URL, options chain fetch pattern, dedupe ด้วย expiry+strike — ห้าม copy โค้ด |
| bodytaylor/xau-oi-lab | live (fb95128) | ❌ ไม่มี license file | แนวทาง: Playwright scrape CME OI intraday bars, SD zones, phase schedule 07:xx ICT |
| Hewkaw02/TVdataOptionOI | live (013e91b) | ✅ **MIT** | ใช้ได้เต็มสิทธิ์ — anonymous TradingView options: chain ครบ 29 คอลัมน์ (strike/type/expiration/dte/iv/delta/…) |

## ผลทดสอบจริงจาก VPS นี้ (27 พ.ย. 2026)

| Source | ผล | หมายเหตุ |
|---|---|---|
| Yahoo Finance (GC=F, DX-Y.NYB) | ✅ ใช้ได้ | GC 3668.4 / DXY 103.7 (yfinance) |
| FRED (DFII10 real yield ฯลฯ) | ✅ ใช้ได้ **ไม่ต้องมี API key** | `fred.stlouisfed.org/graph/fredgraph.csv?id=DFII10` |
| CFTC Disaggregated COT API | ✅ ใช้ได้ | dataset 6dca-aqww, gold code `cftc_contract_market_code=088691`, ข้อมูลถึง 2026-11-17: MM long 210,051 / short 43,919 / OI 407,834 (net MM เฉียบลงจาก +190k เป็น +166k) — หมายเหตุ: ชื่อ field ต้องมี prefix ครบ (`cftc_contract_market_code` ไม่ใช่ `contract_market_code`) |
| TVdataOptionOI → COMEX:GC1! | ✅ chain ได้ (6,114 contracts, IV+delta จริง) **แต่ open_interest = None ทั้งหมด** | TV scanner ส่ง field open_interest แล้วแต่ TV ไม่มีข้อมูล OI ของ GC options |
| CME direct (CmeWS/mvc) | ❌ **403 IP blocked** | "blocked due to suspected web scraping" + ToU ห้าม scraping ชัดเจน — ห้ามลองซ้ำจาก server นี้ |
| CME Vol2Vol / QuikStrike (มี free CME account) | ⚠️ ทำได้ด้วย browser automation (แบบ Gold-Sight) แต่ติด ToU + CME login challenge | Gold-Sight รันบน GitHub Actions เลี่ยง IP block — ถ้าจะทำต้องใช้ credentials ของ Poom + ตัดสินใจเรื่อง ToU เอง |
| World Gold Council ETF flows | ❌ ไม่มี API ฟรี | MVP = manual CSV import |

## ดังนั้นแผนข้อมูล MVP

- **Automated (แน่นอน):** OHLC gold/DXY (Yahoo), real/normal yields (FRED), COT MM positioning (CFTC), ATM IV + 25Δ risk reversal + implied weekly range (TVdataOptionOI → คำนวณจาก IV/delta เอง)
- **Manual import ช่วงแรก (มี adapter interface รอ):** OI by strike (QuikStrike CSV export), ETF flows (WGC xlsx/CSV)
- **ทางเลือกอนาคต:** CME browser collector ด้วย free CME account — ต้องคุยเรื่อง ToU + credentials ก่อน (ค้างการตัดสินใจของ Poom)

## ข้อสังเกตด้านกฎ
- ไม่มี license หมายถึงสงวนลิขสิทธิ์ไว้ตามปริยาย — อ่านเพื่อเรียนรู้แนวคิดได้ คัดลอกโค้ดไม่ได้
- TVdataOptionOI (MIT) จะ vendored เป็น dependency ของ collector ของเรา
- CME ToU: data ของ CME ใช้ personal/non-commercial ได้ผ่าน account แต่การ scrape อัตโนมัติโดน 403 จาก VPS — ถ้าจะทำควรรันบน GitHub Actions (IP บ้านของ runner) แบบ Gold-Sight
