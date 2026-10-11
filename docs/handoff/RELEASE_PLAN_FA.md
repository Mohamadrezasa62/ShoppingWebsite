# پلن ریلیز و کارهای باقی‌مانده

مرجع برنامهٔ اصلی: ../DEVELOPMENT_ROADMAP.md. مرجع شرح اجرای واقعی: ../releases/IMPLEMENTATION_STATUS.md. مراحل زیر شمارهٔ R هستند؛ checkpointهای توسعه شمارهٔ milestone پذیرفته‌شده نیستند.

| مرحله | وضعیت فعلی | باقیماندهٔ پذیرش |
|---|---|---|
| R0 قرارداد/baseline | بخشی اجرا شده | تصمیم تجاری، UX، OpenAPI و baseline PostgreSQL |
| R1 هویت/زیرساخت | بخشی اجرا شده | SMS واقعی، forgot-password، staging/alerts/storage |
| R2 کاتالوگ | بخشی اجرا شده | CDN، retention، کیفیت داده و شواهد موبایل |
| R3 فروشنده/موجودی | بخشی اجرا شده | مدارک KYC، بانک و concurrency PostgreSQL |
| R4 خرید/سفارش | بخشی اجرا شده | سیاست مالیات/invoice رسمی، guest، gift card و تست race |
| R5 پرداخت | core اجرا شده؛ پذیرش خارجی باز | تأیید واقعی provider، reconciliation، unknown initiation و refund واقعی |
| R6 fulfillment | بخشی اجرا شده | carrier، لغو paid در سطح واحد، اعلان خارجی و سیاست مرجوعی |
| R7 مالی | بخشی اجرا شده | payout واقعی، تطبیق، دفتر مالی و سیاست تسویه |
| R8 اعتماد/محتوا | بخشی اجرا شده | review gate محتوا، draft موازی، redirect و retention |
| R9 رشد | بخشی اجرا شده | loyalty، کانال خارجی، A/B و analytics funnel |
| R10 دروازه انتشار | پذیرفته نشده | stack واقعی، امنیت/بار/restore/E2E و pilot |
| R11 دامنه تکمیلی | بخشی اجرا شده | chat، روش‌های پرداخت تکمیلی، حذف قانونی، localization و integrations |
| R12 مقیاس | پایه اجرا شده | search مستقل، native apps، بار PostgreSQL و multi-region |

## توالی ریلیزها

1. **Infrastructure staging:** D1–D8؛ بدون سفارش واقعی. کد immutable، env خصوصی، CI واقعی و restore.
2. **Transactional pilot:** رفع P0های پرداخت/SMS/حمل/refund/payout/KYC/مالیات؛ سفارش محدود واقعی و تطبیق روزانه. هنوز همهٔ دامنهٔ گزارش کامل نیست.
3. **Public commerce:** پذیرش R10، مسائل بحرانی صفر، پایش و support فعال و سیاست‌های عمومی. دامنهٔ عرضه باید صریح باشد؛ امکانات حذف‌شده از دامنه «تکمیل» نامیده نشوند.
4. **Full feature releases:** باقیمانده‌های R0–R9 و R11 به بسته‌های کوچک با API/UI/test/migration/doc و پذیرش اختصاصی تقسیم شود.
5. **Scale releases:** R12 بر اساس بار اندازه‌گیری‌شده و نیاز واقعی، نه صرفاً افزایش تعداد سرویس‌ها.

## ثبت پذیرش هر ریلیز

برای هر ردیف backlog: شناسهٔ requirement، مالک، dependency، تغییر کد، تست، نتیجه، ریسک باز و تصمیم پذیرش ثبت شود. هر ریلیز باید release SHA/tag، backup/restore evidence، migration plan، rollback compatible، نتیجهٔ CI/E2E و تنظیمات بدون secret داشته باشد. بدون اجرای واقعی نتیجهٔ pass درج نشود. کنترل‌های launch موجود تنها پس از بسته شدن نیازها در سورس و شواهد با تست مناسب بازنگری شوند.

این بسته snapshot قابل تحویل است؛ production release، merge به main و تکمیل R0–R12 محسوب نمی‌شود.
