# ADR 0001: Service/Repository Boundary

## Status
Accepted

## Context
- پروژه در سرویس‌ها شامل query مستقیم دیتابیس، business rule و rendering concern شده بود.
- حذف شدن پوشه `repository` باعث coupling بالا و سختی تست regression شد.
- هدف refactor: بازگشت مرز معماری بدون تغییر رفتار عملیاتی.

## Decision
- لایه `server/app/repositories` به‌عنوان مرز رسمی دسترسی به دیتابیس نگه‌داری می‌شود.
- Repository فقط برای عملیات low-level مجاز است:
  - query
  - join/projection تکراری
  - CRUD/upsert/delete
- Business logic در `server/app/services` باقی می‌ماند:
  - policyهای scheduling
  - ruleهای `GREEN/YELLOW/RED`
  - publish/finalize/permission flow
- Pageهای Streamlit مجاز به query مستقیم نیستند و باید از serviceها استفاده کنند.

## Consequences
- تست واحد repository ساده‌تر و مستقل‌تر می‌شود.
- serviceها خواناتر و قابل نگه‌داری‌تر می‌شوند.
- خطر تغییر ناخواسته رفتار با refactor کاهش می‌یابد.
- برای هر query جدید باید ابتدا repository contract تعریف شود.
