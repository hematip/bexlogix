# Development Guide

## Setup
1. Create and activate virtualenv.
2. Install dependencies:
   - `pip install -r requirements.txt`
3. Run app:
   - `streamlit run client/streamlit_app.py`

## Seed Data Regeneration
- اگر فایل‌های `data/*.xlsx` در محیط شما موجود نبودند، قبل از اولین اجرا می‌توانید این دستور را بزنید:
  - `python server/db/generate_sample_files.py`
- در startup هم اگر فایل‌های seed لازم پیدا نشوند، سامانه آن‌ها را خودکار بازتولید می‌کند.

## Test Taxonomy
- `unit`: منطق خالص و سریع (بدون side effect سنگین)
- `service`: رفتار سرویس‌ها و flowهای domain
- `integration`: تست‌های دیتابیس/یکپارچگی
- `smoke`: تست‌های عملیاتی سبک برای sanity کلی

## Test Commands
- همه تست‌ها:
  - `pytest -q`
- فقط unit:
  - `pytest -m unit -q`
- فقط service + integration:
  - `pytest -m "service or integration" -q`
- فقط smoke:
  - `pytest -m smoke -q`

## Quality Gate
- اسکریپت کیفیت:
  - `python scripts/quality_gate.py`
- قوانین فعلی:
  - منع query مستقیم در `client/pages`
  - منع import سرویس داخل repository
  - سقف طول تابع در repository
  - سقف طول فایل در service

## Refactor Guardrails
- در repository هیچ business rule پیاده‌سازی نشود.
- در pageها access مستقیم به ORM/SQL نداشته باشیم.
- تغییرات clean-code نباید خروجی endpoint/UI flow را عوض کند.
