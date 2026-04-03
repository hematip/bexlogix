# Daily Visitor Status Import Contract

## Purpose
فایل روزانه منبع اصلی وضعیت روز کاری ویزیتورها برای ساخت مسیر است.

## Required Columns
- `work_date`
- `username`
- `visitor_code`
- `full_name`
- `start_lat`
- `start_lon`
- `capacity`
- `is_active_today`

## Mapping Rules
- نگاشت معتبر با `username + visitor_code` انجام می‌شود.
- `username` باید در جدول users با نقش `visitor` وجود داشته باشد.
- `start_lat` و `start_lon` باید هر دو همزمان مقدار داشته باشند.
- `capacity` باید عدد صحیح و غیرمنفی باشد.

## Side Effects
- پروفایل ویزیتور (visitor profile) در صورت نیاز update/upsert می‌شود.
- وضعیت روزانه (`daily_visitor_status`) برای تاریخ مربوطه upsert می‌شود.

## Notes
- فایل users/password از UI آپلود نمی‌شود و مرجع ثابت است.
- startup seed فقط users + stores را preload می‌کند.
