# پلن دیپلوی و عملیات

وضعیت: زیرساخت staging نوشته شده؛ میزبان، دامنه، کلیدها و اجرای stack واقعی ارائه نشده است. راهنمای فرمان‌ها: ../releases/DEPLOYMENT.md. Compose توسعه را با production ترکیب نکنید.

| گام | کار باقی‌مانده | مسئول پیشنهادی | شرط عبور |
|---|---|---|---|
| D1 | انتخاب میزبان Linux، DNS، ظرفیت دیسک و منابع، ثبت مالک عملیات | DevOps | DNS درست، 80/443 قابل دسترس، volumes پایدار |
| D2 | نصب Docker/Compose سازگار؛ secrets خصوصی و origin/host تنظیم شود | DevOps | config --quiet و preflight موفق؛ بدون افشای env |
| D3 | اجرای workflow و تست‌های PostgreSQL/Redis در checkout تمیز | QA/Backend | همهٔ integrationها اجرا و موفق؛ شکست/skip توضیح داده شود |
| D4 | build، DB/Redis، release job، API/worker/beat/frontend/edge | DevOps | migration/seed_roles/collectstatic/preflight services موفق |
| D5 | تست گواهی واقعی، secure cookies، CSRF، proxy trust، SSR، رسانه و نقش‌ها | QA/Security | مشتری/فروشندهٔ دیگر دسترسی نداشته باشد؛ raw media بسته |
| D6 | پایش worker و beat، صف/خطا/ظرفیت/backup و alerts | Operations | خرابی آزمایشی هشدار بدهد؛ تنها یک beat فعال باشد |
| D7 | backup خارج میزبان و restore در DB دورریختنی؛ migration/rollback rehearsal | DevOps/Finance | restore واقعی و consistency بدون نقص مستند |
| D8 | E2E موبایل/RTL، بار نماینده، بررسی امنیت و dependencyها | QA/Security | شواهد و مسائل بحرانی بسته شود |
| D9 | دروازهٔ فروش و pilot محدود | Product/Finance | تمام شرط‌های SALES_LAUNCH_PLAN_FA.md محقق شود |

## فرمان staging جدید

از ریشه پروژه، پس از تکمیل خصوصی .env.production:

```bash
docker compose --env-file .env.production -f compose.production.yaml config --quiet
docker compose --env-file .env.production -f compose.production.yaml build api frontend
docker compose --env-file .env.production -f compose.production.yaml up -d --wait db redis
docker compose --env-file .env.production -f compose.production.yaml run --rm release
docker compose --env-file .env.production -f compose.production.yaml up -d --wait api worker beat frontend edge
```

/health/ فقط liveness است. /ready/، DB و Redis را می‌سنجد؛ کارکرد worker و درگاه را ثابت نمی‌کند. بررسی preflight --launch فعلاً به علت دروازه‌های باز عمداً ناموفق است؛ آن را حذف یا bypass نکنید تا فروش فعال شود.

## ارتقا و برگشت

ورودی نوشتن را متوقف، API/worker/beat را متوقف و backup سازگار DB/media/config تهیه کنید. restore آزمایشی، image tag سازگار و migration plan را بررسی کنید؛ release job شکست بخورد انتشار متوقف بماند. پس از سلامت و consistency نوشتن باز شود. rollback کد فقط با schema سازگار؛ بعد از پرداخت واقعی restore دیتابیس قدیمی بدون تطبیق مالی مجاز نیست. docker down -v راه rollback نیست.

این فایل برنامه است؛ هیچ‌یک از D1 تا D9 با وجود فایل YAML به‌تنهایی پذیرفته نمی‌شود.
