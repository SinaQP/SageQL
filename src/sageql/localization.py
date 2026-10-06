"""Host-selected presentation language; never normalize SQL values or identity."""

from __future__ import annotations


def validate_language(language: str) -> str:
    if language not in ("fa", "en"):
        raise ValueError("language must be fa or en")
    return language


def language_instructions(language: str) -> str:
    validate_language(language)
    return (
        " Write all user-facing prose, understanding, summaries, clarification questions "
        "and unsupported explanations in Persian (fa), even when the user writes in English. "
        if language == "fa" else
        " Write all user-facing prose, understanding, summaries, clarification questions "
        "and unsupported explanations in English (en). "
    ) + (
        "Understand Persian conversation, informal phrasing and multi-turn refinements, "
        "including Persian digits ۰۱۲۳۴۵۶۷۸۹, Arabic-Indic digits ٠١٢٣٤٥٦٧٨٩, "
        "Arabic/Persian letter variants ي/ی and ك/ک, and zero-width non-joiners. "
        "For example سلام is a greeting, اسم کارکنان را بده requests employee names, "
        "به تفکیک کارمند refines grouping, and فقط علی requests a filter when registered. "
        "Recognize امروز, دیروز and ماه قبل as relative period requests within the "
        "declared calendar. Language never changes calendar semantics. "
        "Keep JSON keys, registered IDs, enum values and ISO dates in their required "
        "machine format; output numeric JSON fields as numbers with ASCII digits. "
        "Preserve literal names and text filter values exactly as supplied; do not "
        "transliterate or replace their letters or digits to guess database values."
    )


GRAINS_FA = {"none": "بدون گروه‌بندی زمانی", "day": "روز", "week": "هفته",
             "month": "ماه", "quarter": "فصل", "year": "سال"}
PERIODS_FA = {"all": "همه تاریخ‌های موجود", "range": "بازه زمانی", "month": "ماه",
              "year": "سال", "today": "امروز", "yesterday": "دیروز",
              "this_week": "این هفته", "last_week": "هفته قبل",
              "this_month": "این ماه", "last_month": "ماه قبل",
              "this_quarter": "این فصل", "last_quarter": "فصل قبل",
              "this_year": "امسال", "last_year": "سال قبل"}


def error_text(code: str, original: str, language: str = "fa") -> str:
    """Localize safe SDK errors by stable code, without exposing raw details."""
    if language == "en":
        return original
    return {
        "access_denied": "دسترسی به این گزارش یا گفت‌وگو برای شما مجاز نیست.",
        "unsupported": "این گزارش در محدوده قابلیت‌های پشتیبانی‌شده نیست. تاریخ‌ها باید میلادی باشند و درخواست باید از اطلاعات ثبت‌شده استفاده کند.",
        "invalid_input": "متن پرسش، شناسه درخواست و نسخه معتبر گفت‌وگو را ارسال کنید.",
        "invalid_spec": "مشخصات گزارش معتبر نیست. پرسش یا بازه زمانی را دقیق‌تر بیان کنید.",
        "invalid_interpretation": "پاسخ مفسر گزارش معتبر نبود. پرسش را دقیق‌تر بیان کنید.",
        "clarification_stalled": "نتوانستم درخواست گزارش با نام کارمند را تفسیر کنم. لطفاً درخواست گزارش را دوباره ارسال کنید.",
        "agent_exhausted": "نتوانستم در مهلت و تعداد تلاش مجاز به تفسیر معتبر درخواست برسم. لطفاً پرسش را دقیق‌تر بیان کنید یا دوباره تلاش کنید.",
        "provider_failed": "تفسیر پرسش انجام نشد. با یک درخواست جدید دوباره تلاش کنید.",
        "provider_unavailable": "مفسر گزارش در دسترس نیست. تنظیمات سرویس مدل را بررسی کنید.",
        "provider_input_limit": "حجم گفت‌وگو یا اطلاعات گزارش بیش از حد مجاز است. گفت‌وگوی تازه‌ای شروع کنید.",
        "execution_disabled": "اجرای گزارش هنوز توسط میزبان فعال نشده است.",
        "database_unavailable": "اتصال به پایگاه داده برقرار نشد. اتصال شبکه یا VPN و تنظیمات پایگاه داده را بررسی کنید و دوباره تلاش کنید.",
        "execution_failed": "اجرای گزارش انجام نشد. اتصال پایگاه داده را بررسی کنید و دوباره تلاش کنید.",
        "adapter_failed": "نتیجه دریافتی از پایگاه داده معتبر نبود.",
        "lookup_failed": "جست‌وجوی کارمند نتیجه معتبر نداد. مشخصات کارمند و تنظیمات منبع را بررسی کنید.",
        "schema_mismatch": "ساختار پایگاه داده با تعریف ثبت‌شده گزارش سازگار نیست.",
        "schema_drift": "ساختار پایگاه داده با تعریف ثبت‌شده گزارش سازگار نیست یا در دسترس نیست.",
        "database_busy": "پایگاه داده گزارش مشغول است. کمی بعد دوباره تلاش کنید.",
        "query_timeout": "زمان مجاز اجرای گزارش به پایان رسید. بازه یا فیلترها را محدود کنید.",
        "query_work_limit": "گزارش از سقف پردازش پایگاه داده عبور کرد. بازه یا فیلترها را محدود کنید.",
        "request_expired": "مهلت این درخواست تمام شده است. برای تلاش دوباره درخواست جدیدی ارسال کنید.",
        "invalid_query": "پرس‌وجوی گزارش تأیید نشد و اجرا نشده است.",
        "storage_failed": "ذخیره یا بازیابی گفت‌وگو انجام نشد. دوباره تلاش کنید.",
        "serialization_failed": "تبدیل نتیجه گزارش انجام نشد.",
        "policy_failed": "دسترسی گزارش قابل بررسی نبود. با میزبان برنامه تماس بگیرید.",
        "request_timeout": "زمان مجاز درخواست به پایان رسید. بازه یا فیلترهای گزارش را محدود کنید.",
        "cancelled": "درخواست گزارش لغو شد.",
        "session_busy": "درخواست دیگری در این گفت‌وگو در حال اجراست. کمی صبر کنید.",
        "request_in_progress": "این درخواست هنوز در حال اجراست. کمی صبر کنید.",
        "revision_conflict": "گفت‌وگو تغییر کرده است. نسخه فعلی آن را دوباره دریافت کنید.",
        "request_conflict": "شناسه درخواست قبلاً با ورودی دیگری استفاده شده است. شناسه جدیدی ارسال کنید.",
        "request_retired": "این درخواست قبلاً پردازش شده و پاسخ ذخیره‌شده آن منقضی شده است.",
        "request_limit": "این گفت‌وگو به سقف درخواست رسیده است. گفت‌وگوی تازه‌ای شروع کنید.",
        "clarification_limit": "حجم پرسش‌ها و پاسخ‌های تکمیلی به حد مجاز رسیده است. پرسش کامل را در گفت‌وگوی تازه‌ای بنویسید.",
        "interrupted_request": "درخواست قبلی متوقف شد. برای تلاش دوباره درخواست جدیدی ارسال کنید.",
        "authentication_required": "با توکن معتبر فضای گزارش‌گیری وارد شوید.",
        "invalid_host": "از نشانی محلی برنامه گزارش‌گیری استفاده کنید.",
        "invalid_origin": "درخواست از این مبدأ مجاز نیست.",
        "invalid_request": "ساختار درخواست معتبر نیست. فقط فیلدهای مجاز را ارسال کنید.",
        "request_too_large": "حجم درخواست بیش از حد مجاز است.",
        "not_found": "مورد درخواستی در دسترس نیست.",
        "host_busy": "فضای گزارش‌گیری مشغول است. کمی بعد دوباره تلاش کنید.",
    }.get(code, "درخواست گزارش انجام نشد. پرسش و تنظیمات گزارش را بررسی کنید و دوباره تلاش کنید.")
