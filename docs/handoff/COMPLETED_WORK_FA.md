# کارهای اجراشده و شواهد

مرجع تفصیلی: ../releases/IMPLEMENTATION_STATUS.md. «اجراشده» در این سند به معنی پیاده‌سازی سورس و آزمون محلی موجود است؛ جای پذیرش production را نمی‌گیرد.

| دامنه | خروجی اجراشده | محدودیت اصلی |
|---|---|---|
| هویت | OTP، session/CSRF، نقش‌ها، پروفایل/آدرس، revoke، تغییر رمز کارکنان، محدودیت درخواست، adapter کاوه‌نگار | تحویل واقعی SMS و بازیابی رمز فراموش‌شده تأیید نشده |
| کاتالوگ | محصول/variant/offer، دسته/برند/facet، پیشنهاد فروشنده، moderation رسانه، CSV، SEO، مجموعه و مقایسه | CDN و retention عملیاتی باقی است |
| فروشنده/موجودی | پنل محدود، انبار، انتقال/تعدیل نسخه‌دار، رزرو/مصرف/بازگشت موجودی، گزارش | مدارک KYC، بانک و تست قفل‌های PostgreSQL باقی است |
| خرید | سبد، کوپن، quote امضاشده، snapshot، مالیات تنظیم‌پذیر، انتخاب ارسال/بازه، سفارش و صورت سفارش | نرخ قانونی/صورتحساب رسمی، guest و gift card کامل نیست |
| پرداخت | sandbox توسعه؛ adapter زرین‌پال پیش‌فرض خاموش، callback معتبر، capture اتمیک، جلوگیری از تکرار، بازیابی مشتری، audit مالی و CSV صفحه‌ای تطبیق با دلیل و سوابق خصوصی پیگیری | پذیرش واقعی، تطبیق بانکی، درخواست نامعلوم و استرداد واقعی باقی است |
| عملیات | صف فروشنده، بسته‌بندی/ارسال، tracking، تحویل مدیر، لغو جزئی گروه ارسال، مرجوعی مقداری | carrier واقعی و refund واقعی کامل نیست |
| مالی | snapshot کمیسیون/تسویه، subledger فروشنده، تأیید دو نفره و گزارش | payout شبیه‌سازی است؛ دفتر کل حسابداری تأیید نشده |
| اعتماد/پشتیبانی | review خرید معتبر و تصویر، Q&A، امتیاز فروشنده، تیکت خصوصی، dispute، risk hold انسانی، pagination و idempotency | chat زنده و fraud scoring پیاده نشده |
| محتوا/رشد | wishlist/follow، سابقهٔ رضایت‌مند، نسخه‌بندی و زمان‌بندی محتوا، اعلان داخلی، campaign، outbox/retry/dead letter | کانال خارجی، loyalty، A/B و funnel باقی است |
| زیرساخت | Compose HTTPS مستقل، runtime غیر root، preflight، readiness، consistency checker، CI نوشته‌شده | اجرای واقعی stack، TLS، restore/load/security/E2E باقی است |

## شواهد آخرین نسخهٔ کد

- 366 تست کشف شده: 336 پاس، 30 skipped (28 وابسته به PostgreSQL، دو Redis).
- typecheck و build تولید frontend موفق؛ تست مرزهای redirect پرداخت موفق.
- makemigrations --check --dry-run: تغییر مدل ثبت‌نشده وجود ندارد.
- git diff --check موفق. هیچ تماس واقعی درگاه/پیامک یا انتقال وجه انجام نشده است.
- نتیجهٔ قبلی runtime standalone با SQLite، HTTP redirect، readiness با TLS header، SSR و sitemap موفق بوده؛ معادل Docker یا TLS واقعی نیست.
- CI، تست‌های PostgreSQL/Redis و مرورگر نوشته شده‌اند اما نتیجهٔ اجرای آن‌ها در این محیط موجود نیست.

برای تکرار تست‌ها از فرمان‌های IMPLEMENTATION_STATUS.md، scripts package.json و workflowهای موجود استفاده کنید؛ skipped را پاس تلقی نکنید. ۲۶ checkpoint شمارهٔ توسعه‌اند، نه پذیرش ۲۴ milestone کسب‌وکار.
