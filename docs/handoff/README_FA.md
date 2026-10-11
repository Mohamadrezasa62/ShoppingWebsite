# تحویل پروژه ShoppingWebsite

تاریخ: 2026-10-11 — شاخه: development/milestone-foundation

این بسته سورس کامل نسخهٔ فعلی است؛ برای آماده‌سازی محیط staging تحویل می‌شود. فروش واقعی و تکمیل تمام milestoneها هنوز پذیرفته نشده است. آخرین بستهٔ کاربردی: سوابق خصوصی پیگیری هر پرداخت با ثبت دلیل، audit و جلوگیری از ثبت تکراری؛ همراه خروجی CSV مالی صفحه‌ای. هیچ‌کدام تأیید پرداخت یا تطبیق بانکی کامل نیستند.

## ترتیب مطالعه

1. COMPLETED_WORK_FA.md — قابلیت‌های اجراشده و شواهد تست.
2. DEPLOY_PLAN_FA.md — دیپلوی مرحله‌ای، کارهای زیرساختی باقی‌مانده و بازگشت.
3. SALES_LAUNCH_PLAN_FA.md — مسیر خرید واقعی و دروازه‌های شروع فروش.
4. RELEASE_PLAN_FA.md — وضعیت R0 تا R12 و برنامهٔ پذیرش ریلیز.
5. ../DEVELOPMENT_ROADMAP.md — برنامهٔ کامل اولیه؛ ارزیابی ابتدای آن تاریخی است.
6. ../releases/IMPLEMENTATION_STATUS.md — شرح ۲۶ checkpoint توسعه و محدودیت‌ها.
7. ../releases/DEPLOYMENT.md و OPERATIONS_RUNBOOK.md — فرمان‌ها و قرارداد عملیاتی.

## محتویات و اجرا

backend: Django و migrations و تست‌ها؛ frontend: Next.js و package-lock؛ deploy و compose.production.yaml: زیرساخت HTTPS؛ .github/workflows: CI و smoke؛ docs و launch: اسناد موجود. نسخهٔ Node و Python را با Dockerfileها هماهنگ کنید. وابستگی‌ها داخل ZIP نیستند و از requirements.txt و npm ci نصب می‌شوند. اطلاعات حقیقی کاربران، کلیدها، node_modules، .next، محیط Python، دیتابیس محلی و تاریخچهٔ .git تحویل نمی‌شوند.

برای staging از compose.production.yaml مستقل استفاده کنید؛ دستورهای دقیق در راهنمای DEPLOYMENT.md موجود است. فایل deploy/production.env.example فقط الگو است و باید در سرور به .env.production خصوصی تبدیل شود. seed_demo فقط توسعه است؛ release فقط نقش‌ها را ایجاد می‌کند. حساب مدیر واقعی باید با فرآیند خصوصی اپراتور ساخته شود.

## وضعیت انتشار

تغییرات محلی commit شده‌اند؛ push، merge به main، اجرای GitHub CI، تهیهٔ گواهی TLS و دیپلوی واقعی در این تحویل انجام نشده‌اند. ZIP snapshot کد است و فایل اجرایی آفلاین یا تضمین فروش آماده نیست. فایل SHA256SUMS.txt داخل ZIP تمام فایل‌های سورس بسته را پوشش می‌دهد.

## ساخت دوبارهٔ ZIP

از checkout تمیزِ ثبت‌شده، با Python استاندارد:

```bash
python scripts/package_release.py --output ../ShoppingWebsite-release-candidate.zip
```

اسکریپت SHA/branch را ثبت و CRC آرشیو و هش هر فایل سورس را بررسی می‌کند. فقط فایل‌های ثبت‌شدهٔ Git بسته‌بندی می‌شوند. این کنترل جای بررسی محرمانگی سورس و پذیرش production را نمی‌گیرد.
