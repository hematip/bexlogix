# Purpose: Shared error types and Persian error message registry.
# Workflow Role: Keeps service-layer failures human-readable for Persian UI surfaces.

from __future__ import annotations


# Contract: BexLogixError defines a typed boundary and should remain behavior-stable.
class BexLogixError(Exception):
    """Base application error for domain/service failures."""


# Contract: ValidationError defines a typed boundary and should remain behavior-stable.
class ValidationError(BexLogixError):
    """Raised when input values fail validation."""


# Contract: DomainError defines a typed boundary and should remain behavior-stable.
class DomainError(BexLogixError):
    """Raised when a business/domain rule is violated."""


# Contract: PermissionError defines a typed boundary and should remain behavior-stable.
class PermissionError(BexLogixError):
    """Raised when the actor is not authorized to perform an action."""


PERSIAN_ERROR_MESSAGES: dict[str, str] = {
    # Assignment service
    "manager_only_generate_publish": "فقط کاربر مدیر اجازه تولید یا انتشار مسیر را دارد.",
    "no_draft_assignments": "برای این تاریخ هیچ مسیر پیش‌نویسی پیدا نشد. ابتدا مسیر را تولید کنید.",
    "non_draft_exists_block_regen": (
        "برای این تاریخ قبلاً مسیریابی انجام شده و وضعیت آن از پیش‌نویس فراتر رفته است "
        "(منتشر/تأییدشده/تکمیل‌شده). برای ساخت دوبارهٔ مسیر، ابتدا از بخش «پاکسازی کامل "
        "داده‌های همین تاریخ» داده‌های فعلی را پاک کنید، سپس مسیر را دوباره بسازید."
    ),
    "draft_exists_for_date": (
        "برای این تاریخ پیش‌نویس فعالی وجود دارد. می‌توانید با گزینهٔ «بازنشانی پیش‌نویس» "
        "آن را جایگزین کنید یا پیش‌نویس فعلی را پاک نمایید."
    ),
    "manager_user_not_found": "کاربر مدیر معتبر پیدا نشد.",
    "supervisor_user_not_found": "کاربر سرپرست معتبر پیدا نشد.",
    "supervisor_only_approve": "فقط کاربر سرپرست اجازه تأیید مسیر را دارد.",
    "publish_concurrent_modification": "انتشار همزمان شناسایی شد. لطفاً صفحه را تازه کنید و دوباره تلاش کنید.",
    "no_draft_for_visitor_approve": "برای این ویزیتور مسیر پیش‌نویس قابل تأیید وجود ندارد.",
    "no_supervisor_approved_to_publish": "مسیر تأییدشده توسط سرپرست برای انتشار وجود ندارد.",
    # Visit service
    "assignment_not_found": "تخصیص موردنظر پیدا نشد.",
    "visit_only_published": "ثبت نتیجه ویزیت فقط برای مسیرهای منتشرشده مجاز است.",
    "visit_only_own_assignment": "شما فقط می‌توانید نتیجه ویزیت مسیرهای خودتان را ثبت کنید.",
    "visit_already_submitted": "نتیجه این ویزیت قبلاً ثبت شده است.",
    "visitor_profile_not_found": "پروفایل ویزیتور مرتبط با این تخصیص پیدا نشد.",
    "manager_only_finalize": "فقط مدیر می‌تواند موارد ثبت‌نشده را نهایی کند.",
    "finalize_unsubmitted_count_mismatch": "تعداد موارد ثبت‌نشده تغییر کرده است. صفحه را تازه کنید و دوباره تلاش کنید.",
    # Telesales service
    "telesales_only_submit": "فقط کاربران فروش تلفنی می‌توانند نتیجه پیگیری را ثبت کنند.",
    "followup_already_finalized": "این پیگیری قبلاً نهایی شده است.",
    "followup_only_for_red": "ایجاد پیگیری فروش تلفنی فقط برای ویزیت قرمز مجاز است.",
    # Routing service
    "route_regen_blocked_published": "برای این ویزیتور مسیر منتشرشده وجود دارد و بازتولید مسیر طبق سیاست سامانه مجاز نیست.",
    # Scheduling service
    "unsupported_store_grade": "سطح فروشگاه پشتیبانی نمی‌شود: {grade}",
    "store_no_active_category": "برای فروشگاه «{store_code}» هیچ دسته محصول فعالی تعریف نشده است.",
    "invalid_visit_result": "نتیجه ویزیت نامعتبر است.",
    "invalid_telesales_outcome": "نتیجه پیگیری فروش تلفنی نامعتبر است.",
    "store_not_found": "فروشگاه موردنظر پیدا نشد.",
    # Import services
    "missing_required_columns": "ستون‌های الزامی فایل ناقص است: {columns}",
    "unknown_usernames": "نام‌های کاربری زیر در جدول کاربران یافت نشد: {usernames}",
    "daily_role_must_be_visitor": "فایل وضعیت روزانه فقط کاربرانی با نقش visitor را می‌پذیرد. مقادیر نامعتبر: {usernames}",
    "invalid_contact_status_values": "مقادیر وضعیت تماس نامعتبر است: {values}",
    "invalid_followup_result_values": "مقادیر نتیجه پیگیری نامعتبر است: {values}",
    "unknown_store_codes": "کد فروشگاه‌های زیر در سیستم وجود ندارد: {store_codes}",
    "unknown_visit_ids": "شناسه‌های ویزیت زیر در سیستم پیدا نشد: {visit_ids}",
    # Auth and generic
    "permission_denied_page": "شما دسترسی لازم برای مشاهده این صفحه را ندارید.",
}


def err(key: str, **kwargs) -> str:
    # Contract: err resolves a stable Persian message template and formats placeholders safely.
    template = PERSIAN_ERROR_MESSAGES.get(key, key)
    try:
        return template.format(**kwargs)
    except Exception:
        return template

