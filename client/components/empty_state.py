# Purpose: Centralized contextual empty-state messages for all roles.
# Workflow Role: Improves UX guidance when operational datasets are empty.

from __future__ import annotations

from client.i18n import t


def get_empty_state_message(role: str, context: str) -> str:
    normalized_role = str(role or "").strip().lower()
    normalized_context = str(context or "").strip().lower()

    mapping = {
        ("visitor", "no_assignments"): t(
            "مسیر شما برای این تاریخ هنوز منتشر نشده است. لطفاً با سرپرست تماس بگیرید یا تاریخ دیگری را انتخاب کنید.",
            "Your route for this date has not been published yet. Contact your supervisor or choose another date.",
        ),
        ("supervisor", "no_assignments"): t(
            "هیچ تخصیصی برای این تاریخ ثبت نشده است. برای ساخت مسیر به داشبورد مدیر مراجعه کنید.",
            "No assignments exist for this date. Use the manager dashboard to build routes.",
        ),
        ("telesales", "no_queue"): t(
            "✅ هیچ پیگیری در انتظار وجود ندارد. کار عالی!",
            "✅ There are no pending follow-ups. Great work!",
        ),
        ("manager", "no_due_stores"): t(
            "فروشگاهی در صف ویزیت وجود ندارد. فایل فروشگاه‌ها را بارگذاری کنید یا تاریخ دیگری را انتخاب کنید.",
            "No stores are currently due for visit. Upload store data or choose another date.",
        ),
        ("manager", "no_assignments"): t(
            "برای این تاریخ هنوز تخصیصی ثبت نشده است. ابتدا فایل وضعیت روزانه را اعمال و مسیر را بسازید.",
            "No assignments are available for this date yet. Apply daily status data and build routes first.",
        ),
        ("manager", "no_pending_telesales"): t(
            "موردی در صف انتظار تماس تلفنی وجود ندارد.",
            "There are no items in the telesales queue.",
        ),
        ("manager", "no_route_for_visitor"): t(
            "برای ویزیتور انتخاب‌شده هنوز مسیری ثبت نشده است.",
            "No route exists yet for the selected visitor.",
        ),
        ("supervisor", "no_visits"): t(
            "برای این تاریخ هنوز نتیجه ویزیتی ثبت نشده است.",
            "No visit results are registered yet for this date.",
        ),
        ("supervisor", "no_telesales"): t(
            "موردی در صف فروش تلفنی وجود ندارد.",
            "There are no items in the telesales queue.",
        ),
    }

    return mapping.get(
        (normalized_role, normalized_context),
        t("داده‌ای برای نمایش در این بخش وجود ندارد.", "No data is available to display in this section."),
    )
