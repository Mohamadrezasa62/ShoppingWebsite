# برنامهٔ توسعهٔ ShoppingWebsite بر اساس milestone

تاریخ بررسی: 2026-10-11  
مبنای کد: `8da3446beccd00b46644973792cf786e05a72364`  
مبنای محصول: گزارش ارائه‌شدهٔ محمدرضا سلمانی و اسناد موجود پروژه.  
وضعیت: برنامهٔ پیشنهادی اجرا؛ پذیرش محصول یا مجوز انتشار محسوب نمی‌شود.

## ۱. هدف و روش اجرا

تحویل یک بازارگاه فارسی، RTL و مناسب موبایل با سه سطح مشتری، فروشنده و مدیریت؛ ابتدا خرید واقعی از کشف محصول تا پرداخت، ارسال و استرداد، سپس امکانات رشد و مقیاس. معماری فعلی Django، Next.js، PostgreSQL، Redis و Celery حفظ می‌شود. شروع دوباره یا تبدیل فوری به microservice در برنامه نیست.

این سند برنامهٔ اجرایی تکمیلی `MILESTONES.md` است. شناسه‌های R0–R12 مستقل از شماره‌های milestone سند قبلی‌اند. سند قبلی و تاریخچهٔ آن حفظ می‌شوند؛ تطبیق شماره‌ها در بخش ۴ آمده است. پنل مدیریت به صورت قابلیت‌های قابل استفاده همراه هر دامنه تحویل می‌شود؛ «تکمیل کل پنل» پیش‌نیاز ساخت کاتالوگ یا سفارش نیست.

هر milestone باید یک جریان قابل نمایش، API، UI مربوط، مجوزهای سمت سرور، migration، آزمون رفتار مهم، مستندات و شواهد پذیرش داشته باشد. وجود مدل یا صفحه به تنهایی به معنی تکمیل نیست.

## ۲. وضعیت فعلی و فاصله تا گزارش هدف

این ارزیابی از خواندن کد و اسناد است؛ آزمون‌ها، build و محیط واقعی در این بررسی اجرا نشده‌اند. نتیجهٔ ۴۳ آزمون و build در `launch/READINESS.md` مربوط به گزارش 2026-10-01 است و نتیجهٔ امروز محسوب نمی‌شود.

| دامنه | موجود در سورس | کار لازم |
|---|---|---|
| زیرساخت | Compose، PostgreSQL، Redis، Celery/beat، health/readiness | CI، seed قابل تکرار، staging، آزمایش PostgreSQL، پشتیبان‌گیری و observability |
| هویت | OTP تلفن، session، CSRF، نقش کارکنان؛ ورود کارکنان با OTP و رمز | SMS واقعی، مدیریت session و پروفایل، سیاست بازیابی/حذف حساب، سخت‌سازی و ثبت وقایع |
| کاتالوگ | Product/Variant/Offer، دسته، برند، facet، media، جست‌وجو | moderation کامل، پیشنهاد محصول فروشنده، SEO، pagination و تضمین کیفیت داده |
| فروشنده | درخواست عضویت، بررسی، عضویت محدود، پیشنهاد قیمت/موجودی | مدارک/KYC، import، سفارشات، ارسال، مالی، تسویه و پشتیبانی |
| سبد و سفارش | سبد حساب‌دار، آدرس، quote، snapshot، رزرو و انقضای سفارش | UI checkout، تخفیف/مالیات، سیاست قیمت، اصلاح آدرس، تکمیل وضعیت‌ها و concurrency واقعی |
| پرداخت | PaymentAttempt، LedgerEntry، مسیر داخلی verified capture | هیچ روش عمومی فعال نیست؛ adapter، callback، reconciliation، refund و UI لازم است |
| ارسال و مرجوعی | OrderDelivery، ReturnCase و serviceهای اولیه | API/UI مشتری و فروشنده، مرجوعی در سطح قلم/تعداد، لغو جزئی و carrier |
| مدیریت | بررسی فروشنده، دسته، نقش کارکنان، audit و خلاصه | مدیریت محصولات، سفارش، مالی، ارسال، محتوا، کمپین و پشتیبانی |
| اعتماد | مدل wishlist و review، خدمت بررسی خرید واقعی | API/UI، moderation، Q&A، مقایسه و امتیاز فروشنده |
| رشد | بخشی از طراحی | کوپن، محتوا، کمپین، اعلان، پیشنهادها و analytics |

## ۳. تصمیم‌های پایه و اصلاح مدل

1. محصول و variant مشترک‌اند؛ قیمت، موجودی، ضمانت و فروشنده متعلق به **Offer** هستند. `Product.seller_id` در گزارش هدف را مستقیماً به مدل فعلی منتقل نکنید؛ چند فروشنده برای یک محصول باید باقی بماند.
2. `OrderDelivery` فعلی پایهٔ گروه ارسال هر فروشنده است. در R0 تصمیم بگیرید آیا SellerOrder جدا برای پذیرش، SLA و تسویه لازم است؛ group ارسال به تنهایی معادل سفارش تجاری فروشنده نیست. رابطهٔ آن‌ها و مهاجرت داده مستند شود.
3. موجودی فعلاً روی Offer و رزرو آن است. در R3/R5، InventoryLocation، Warehouse و Reservation مستقل با قید یکتا و migration اضافه شوند؛ مقدارها دو منبع حقیقت نداشته باشند.
4. مبلغ داخلی فعلاً integer toman است. واحد همهٔ APIها، rounding، تبدیل ریال در adapter، حدود مبلغ و قواعد مالیاتی صریح شوند. از float برای پول استفاده نشود.
5. Order فعلی فقط pending/expired/paid/cancelled دارد. وضعیت پرداخت، fulfillment و return مستقل بمانند؛ وضعیت سفارش از اجزای آن محاسبه شود. admin اجازهٔ تغییر آزاد به هر status نداشته باشد.
6. ReturnCase فعلی به delivery متصل است. برای مرجوعی جزئی، ReturnLine با order line و quantity و سقف تجمیعی اضافه شود؛ مبلغ استرداد را سرور محاسبه کند.
7. ledger فعلی نقطهٔ شروع است. seller، line allocation، Refund، Settlement و Payout با reference یکتا و adjustmentهای غیرقابل بازنویسی لازم‌اند؛ طراحی توازن دفتر مالی با مالک مالی بررسی شود.
8. session و CSRF فعلی برای وب حفظ شوند. JWT/OAuth فقط با نیاز مشخص اپ موبایل یا client خارجی اضافه شود؛ تغییر احراز هویت پیش‌نیاز تکمیل فروشگاه نیست.

## ۴. توالی، برآورد و مسئولیت

فرض برآورد: دو توسعه‌دهندهٔ backend، دو frontend، یک QA، همراه DevOps نیمه‌وقت و مالک محصول/طراح. زمان‌ها شامل تکمیل قابلیت، review و QA هستند؛ منتظر ماندن قراردادها را شامل نمی‌شوند. هفته‌ها نسبی از شروع رسمی‌اند، موعد قطعی نیستند. در پایان R0 با backlog واقعی بازبرآورد شود.

| مرحله | بازهٔ پیشنهادی | وابستگی | مالک اجرایی | تطبیق سند قدیمی |
|---|---|---|---|---|
| R0 قرارداد محصول و baseline | هفته ۱–۲ | — | Product + Tech lead | ۱ |
| R1 زیرساخت و هویت | ۳–۴ | R0 | Backend + DevOps | ۲ + بخشی از ۳ |
| R2 کاتالوگ و مدیریت آن | ۵–۷ | R1 | Catalog + Frontend | ۴ + بخشی از ۳ |
| R3 فروشنده و موجودی | ۸–۱۰ | R2 | Marketplace | ۵ + بخشی از ۳ |
| R4 checkout و سفارش | ۱۱–۱۳ | R2، R3 | Commerce | ۶ |
| R5 پرداخت و تطبیق | ۱۴–۱۷ | R4 + دسترسی provider | Payments + Finance | ۷ |
| R6 ارسال، لغو، مرجوعی | ۱۸–۲۰ | R3–R5 | Operations | ۸ |
| R7 کمیسیون و تسویه | ۲۱–۲۳ | R5، R6 | Finance + Backend | بخشی از ۳، ۵، ۷ |
| R8 اعتماد، پشتیبانی و محتوا | ۲۴–۲۵ | R2، R6 | Frontend + Operations | بخشی از ۳، ۹ |
| R9 بازاریابی و رشد اولیه | ۲۶–۲۷ | R4، R8 | Growth + Commerce | ۹ |
| R10 دروازهٔ انتشار | ۲۸–۳۰ | R1–R9 | QA + DevOps + Product | ۱۰ |
| R11 تکمیل دامنهٔ گزارش | پس از انتشار؛ هر بسته جدا برآورد شود | R10 + سیاست کسب‌وکار | Product + Domain owners | بخشی از ۱۱ |
| R12 مقیاس و کانال‌های جدید | با دادهٔ واقعی | R10 + اندازه‌گیری | Platform | ۱۱ |

R0→R1→R2→R3→R4→R5→R6→R7→R10 مسیر اصلی معاملات است. R8/R9 پس از آماده شدن وابستگی‌هایشان می‌توانند موازی انجام شوند. کار طراحی، آماده‌سازی محتوا و اخذ قراردادها از R0 آغاز شود. پیشنهاد بودجهٔ برنامه: ۱۵–۲۰٪ ذخیرهٔ زمانی برای اصلاحات یکپارچه‌سازی؛ با این ذخیره افق کاری حدود ۳۵–۳۶ هفته است. این عدد تضمین موعد نیست.

نقطهٔ هدف: beta تراکنشی محدود پس از R7 و گذر چک‌های امنیت، بازیابی و خرید/استرداد؛ انتشار عمومی پس از R10. تا قبل از پذیرش پرداخت و عملیات، محیط demo سفارش واقعی نپذیرد.

## ۵. milestoneهای اجرایی

### R0 — قرارداد محصول، طراحی و baseline

**خروجی:** backlog اولویت‌دار و traceability گزارش به ticket؛ نقشهٔ customer/seller/admin؛ wireframeهای RTL و design tokens؛ ADRهای مدل و API؛ ماتریس نقش‌ها و eventها؛ ثبت نتیجهٔ اجرای واقعی کد موجود.

**کارها:**
- راه‌اندازی تمیز Compose؛ اجرای تست backend، migration check، typecheck و build؛ ثبت تفاوت رفتار SQLite/PostgreSQL و ایرادات موجود.
- تثبیت بازار ایران، زبان فارسی، دسته‌های launch، merchant of record، fulfillment، مهلت رزرو/مرجوعی، لغو، tax، commission و settlement.
- تعیین endpointهای canonical و mapping از گزارش به API فعلی؛ OpenAPI، error envelope، pagination، sort، ownership و idempotency.
- طراحی جریان‌های شکست: کمبود موجودی، قیمت جدید، payment timeout، late capture، seller suspension، لغو جزئی و refund ناموفق.
- معرفی مالک و موعد برای gateway، SMS، carrier، object storage، دامنه، حقوقی و دادهٔ اولیه.

**پذیرش:** یک محصول با دو فروشنده و یک سفارش با دو گروه ارسال در قرارداد داده و UX مدل شود؛ هر تصمیم باز مالک داشته باشد؛ baseline قابل تکرار ثبت شود؛ هیچ بخش موجود بدون شواهد «کامل» اعلام نشود.

### R1 — محیط قابل اتکا و هویت

**خروجی:** dev/test/staging، pipeline CI، fixture/seed، هویت مشتری و کارکنان، skeleton سه سطح UI.

**کارها:** SMS adapter و rate limit OTP/login؛ expiry و revoke session؛ پروفایل و آدرس با ownership؛ RBAC هر درخواست و seller membership؛ بازیابی امن دسترسی کارکنان و ثبت تغییر نقش؛ request ID و error tracking؛ secrets، health worker و scheduler، storage adapter و قواعد upload؛ backup اولیه و migration rollout.

**پذیرش:** fresh clone با فرمان‌های مستند بالا بیاید؛ CI روی PostgreSQL تست کند؛ مشتری نتواند دادهٔ مشتری دیگر و فروشنده نتواند دادهٔ فروشندهٔ دیگر را بخواند/تغییر دهد؛ console OTP در production ممنوع باشد؛ provider secret در browser/log نباشد.

### R2 — کاتالوگ، discovery و عملیات محصولات

**خروجی:** کاتالوگ آمادهٔ فروش، صفحهٔ دسته/محصول، جست‌وجو و پنل مدیریت کاتالوگ.

**کارها:** taxonomy، برند، specification و attribute schema؛ variant/SKU و slug uniqueness؛ proposal و moderation؛ مدیریت media و فایل غیرمجاز؛ import job با preview/error report؛ جست‌وجو، suggestion، facet، sort، pagination و empty/loading/error states؛ SEO title/description/canonical، sitemap و redirect؛ مقایسهٔ offerها، قیمت و availability؛ publish rules و audit.

**پذیرش:** مشتری روی موبایل variant صحیح را انتخاب و offer دو فروشنده را مقایسه کند؛ محصول ردشده و رسانهٔ غیرمجاز عمومی نشوند؛ دسته/فیلتر با دادهٔ واقعی درست کار کند؛ مدیر بدون SQL بتواند محصول را بررسی و منتشر کند؛ query count و زمان پاسخ اندازه‌گیری شوند.

### R3 — فروشنده، KYC و موجودی

**خروجی:** onboarding کامل، مدیریت offer، مدل مکان موجودی و portal فروشنده.

**کارها:** مدارک و دسترسی محدود به آن‌ها، اطلاعات بانکی و فرایند review؛ approved/suspended enforcement؛ پیشنهاد محصول جدید یا اتصال به variant؛ import/export با validation و محدودیت؛ Warehouse/InventoryLocation/Reservation، stock adjustment audit؛ جلوگیری از کاهش موجودی به زیر رزرو؛ اعلان کمبود؛ seller membership و نقش‌های داخلی.

**پذیرش:** فروشندهٔ تأییدنشده منتشر نکند؛ فروشندهٔ A نتواند offer/مدارک/موجودی B را ببیند؛ import ناقص داده را بی‌صدا خراب نکند؛ موجودی قابل فروش بعد از adjustment و reservation صحیح باشد؛ اطلاعات تجاری صرفاً با ورود فرم «تأییدشدهٔ خارجی» تلقی نشود.

### R4 — سبد، checkout و سفارش قابل اعتماد

**خروجی:** checkout UI، quote معتبر، parent order و گروه‌های فروشنده، مدیریت سفارش اولیه.

**کارها:** سبد فعلی، quantity limits، saved-for-later؛ guest cart و merge در صورت انتخاب دامنهٔ launch؛ ویرایش/حذف آدرس؛ delivery eligibility/method و quote expiry؛ engine تخفیف/مالیات/هزینه با snapshot؛ idempotency payload fingerprint؛ snapshot کامل خطوط؛ رزرو با lock و expiration؛ history/timeline/invoice پایه؛ سیاست بازگرداندن سبد پس از failure؛ admin search/filter/pagination.

**پذیرش:** دو checkout همزمان برای آخرین واحد روی PostgreSQL فقط یک رزرو موفق بسازند؛ تکرار confirm سفارش دوم نسازد و همان key با payload متفاوت رد شود؛ expiry دوبار موجودی آزاد نکند؛ تغییر قیمت offer سفارش قبلی را تغییر ندهد؛ جمع line/discount/tax/shipping دقیقاً برابر total باشد؛ پرداخت هنوز فقط پشت feature flag مجاز فعال شود.

### R5 — پرداخت، refund و reconciliation

**خروجی:** حداقل یک درگاه کارت قابل استفاده، ledger و صف تطبیق، UI پرداخت و transaction admin.

**کارها:** checkout initiation و adapter، callback/webhook احراز‌شده و verify سمت سرور؛ currency conversion؛ retry با deduplication؛ ledger capture/refund؛ Refund request/result؛ reconciliation schedule و review queue؛ timeout/late capture policy؛ secret rotation؛ refund جزئی/کامل طبق قرارداد؛ Tara/SnappPay/DigiPay به عنوان adapterهای مستقل فقط پس از دسترسی رسمی.

**پذیرش:** success، rejection، timeout، callback تکراری/نامرتب، بازگشت browser قبل/بعد callback، amount mismatch، پرداخت دیررس و crash میان verify/commit آزموده شوند؛ تنها verified capture سفارش را paid کند؛ refund تکراری خروجی مالی دوم نسازد و جمع آن از capture بیشتر نشود؛ integration خارجی بدون certification کامل اعلام نشود.

**دروازهٔ تجاری:** مدارک، merchant approval، sandbox و پایلوت live درگاه نخست برای launch ضروری‌اند. فعال‌سازی سه provider اعتباری برای launch پیش‌فرض الزامی نیست؛ هرکدام وضعیت و پذیرش مستقل دارد. اگر مالک محصول هر چهار مورد را الزامی کند، موعد launch به دسترسی آن‌ها وابسته می‌شود.

### R6 — fulfillment، لغو، مرجوعی و پشتیبانی معاملات

**خروجی:** seller order queue، packing/label/tracking، customer tracking و RMA، admin casework.

**کارها:** پذیرش سفارش و SLA فروشنده؛ وضعیت ارسال و تجمیع parent؛ seller/platform fulfillment؛ حداقل tracking دستی معتبر، carrier adapter اگر قرارداد موجود باشد؛ cancellation قبل/بعد capture؛ ReturnLine در سطح قلم/تعداد، eligibility/evidence/inspection؛ restock پس از بررسی، refund orchestration؛ اعلان پیامکی/ایمیلی retryable؛ ticket مرتبط با order.

**پذیرش:** در سفارش دو فروشنده، یک shipment تحویل شود و دیگری لغو/مرجوع گردد بدون خراب شدن مبلغ یا موجودی؛ مرجوعی همان quantity دوباره پذیرفته نشود؛ هر transition غیرمجاز رد شود؛ لغو پرداخت‌شده refund قابل پیگیری بسازد؛ مشتری timeline منسجم ببیند؛ seller به خطوط نامرتبط دسترسی نداشته باشد.

### R7 — کمیسیون، تسویه و governance مالی

**خروجی:** دفتر مطالبات فروشنده، صورت‌حساب، settlement دوره‌ای، payout review و گزارش مدیریت.

**کارها:** commission effective dates و snapshot هر خط؛ allocation تخفیف/ارسال/مالیات/refund؛ payable و hold برای مرجوعی/dispute؛ Settlement/SettlementLine/Payout، حساب مقصد تأییدشده؛ کنترل دو نقش مستقل برای payout حساس؛ اصلاحات با adjustment؛ گزارش fee/net sales؛ reconciliation payout با بانک/provider؛ CSV export با کنترل دسترسی.

**پذیرش:** مثال عددی دو فروشنده با تخفیف و refund جزئی تا ریال/تومان مصوب تراز شود؛ refund پس از settlement adjustment بسازد؛ اجرای مجدد batch دوباره پرداخت نکند؛ seller فقط صورت‌حساب خود را ببیند؛ payout ناموفق/نامعلوم تا تأیید نهایی «موفق» نشان داده نشود.

### R8 — اعتماد، محتوا و پشتیبانی عمومی

**خروجی:** wishlist، review/Q&A، help center و صف پشتیبانی/اختلاف، CMS پایه.

**کارها:** اتصال review service موجود به API/UI، تصویر و moderation، verified purchase؛ امتیاز فروشنده با قواعد شفاف؛ Q&A و ضداسپم؛ comparison محصول/variant؛ home sections، banner، collection، راهنمای خرید/وبلاگ و policy؛ ticket assignment، escalation و dispute evidence؛ audit و دسترسی support به حداقل اطلاعات لازم.

**پذیرش:** review خرید تأییدنشده رد شود؛ تصویر/متن در انتظار بررسی منتشر نشود؛ مشتری فقط پروندهٔ خود را ببیند؛ شکایت با مسئول و timeline قابل پیگیری باشد؛ محتوا روی موبایل RTL خوانا و SEO آن قابل بررسی باشد.

### R9 — رشد اولیه و ابزارهای بازاریابی

**خروجی:** کوپن، کمپین زمان‌بندی‌شده، اعلان‌ها، merchandising و funnel analytics.

**کارها:** coupon eligibility/usage/cap/stacking؛ رقابت همزمان روی آخرین ظرفیت coupon؛ flash sale و collection، upsell/cross-sell قاعده‌ای؛ notification preferences، back-in-stock/price-drop؛ recently viewed و recommendation پایه؛ eventهای view→cart→checkout→payment→delivery؛ bot exclusion و privacy؛ گزارش sales/conversion/return برای seller/admin.

**پذیرش:** quote و confirm یک قانون تخفیف داشته باشند؛ ظرفیت/بودجهٔ کمپین در concurrency تجاوز نکند؛ پیام با consent و deduplication ارسال شود؛ refund سهم تخفیف را درست محاسبه کند؛ event خرید با callback تکراری دوباره شمرده نشود.

### R10 — دروازهٔ انتشار عمومی

**خروجی:** گزارش پذیرش، محیط production، runbook، پایلوت و rollback plan.

**کارها:** security/RBAC/upload/CSRF review؛ تست PostgreSQL و E2E browser؛ load و worker saturation؛ TLS و secure cookie و تنظیم proxy؛ object storage/CDN؛ backup/restore و migration rehearsal؛ log/metric/trace و alert؛ UX/accessibility/RTL، browser/mobile؛ پشتیبانی، محتوای قانونی و مسئول عملیات؛ rollout درصدی با feature flag.

**اهداف پیشنهادی که در R0 باید تثبیت شوند:**
- در load نمایندهٔ launch: p95 خواندن catalog حداکثر ۵۰۰ms و checkout محلی حداکثر ۱s، بدون زمان provider؛ خطای server کمتر از ۱٪. تعداد request، اندازهٔ catalog، cache و سخت‌افزار آزمون ثبت شود.
- هدف دسترس‌پذیری ماهانه 99.9٪؛ RPO حداکثر ۱۵ دقیقه و RTO حداکثر ۲ ساعت، مشروط به بودجه و معماری مصوب.
- نبود نقص critical/high حل‌نشده در دسترسی، پول و موجودی؛ رفع خطاهای deployment check یا ثبت waiver مشخص و مستدل توسط مالک مسئول.

**پذیرش:** خرید و استرداد واقعی محدود با فروشندهٔ پایلوت موفق باشد؛ restore در محیط جدا با اندازه‌گیری زمان و صحت سفارش/ledger انجام شود؛ رویداد payment timeout و queue failure alert ایجاد کند؛ rollback/migration strategy عملی باشد؛ مالک محصول، فنی، QA، مالی و عملیات شواهد حوزهٔ خود را بپذیرند. «build موفق» مجوز launch نیست.

### R11 — تکمیل امکانات باقی‌ماندهٔ گزارش

این موارد حذف نشده‌اند؛ هر بسته backlog، مالک، API/UI و معیار پذیرش مستقل می‌گیرد:

| بسته | امکانات | شرط و معیار پذیرش |
|---|---|---|
| حساب و privacy | social login، export/delete account، guest checkout اگر عقب افتاد | بازیابی/لینک هویت امن؛ حذف یا ناشناس‌سازی با حفظ رکورد مالی لازم؛ سفارش مهمان فقط با proof امن قابل دسترسی |
| پرداخت پیشرفته | saved payment token، gift card، wallet/credit | فقط token مجاز provider؛ ذخیرهٔ PAN/CVV در پروژه نباشد؛ ledger و charge/refund تراز شوند |
| وفاداری | loyalty، referral، membership | earning/reversal/expiry و تقلب referral آزموده شود |
| رشد پیشرفته | follow seller/brand، bundle، A/B testing، segmentation، push | consent، attribution و تخصیص پایدار آزمایش؛ metric موفقیت قبل از اجرا |
| پشتیبانی پیشرفته | chat، risk rules، fraud flags | حداقل‌سازی اطلاعات، escalation و manual review؛ تصمیم ریسک قابل پیگیری |
| محلی‌سازی | چند زبان/ارز، tax/address منطقه‌ای | عدم جمع چند ارز در یک order؛ قواعد rounding و نرخ snapshot |
| integrations | ERP، accounting، courier sync گسترده | قرارداد داده، outbox، replay، deduplication و reconciliation |

### R12 — مقیاس و کانال‌های جدید

**خروجی مشروط به داده:** search engine مستقل، personalization، advanced analytics، native app API/push، event-driven extraction، logistics پیشرفته و در صورت نیاز multi-region.

**قاعده:** ابتدا profiling و index/cache؛ سپس search مستقل با reindex و permission/filter صحیح؛ outbox و dead-letter/replay قبل از جدا کردن service. multi-region فقط با طراحی سازگاری موجودی/پول، residency و disaster recovery. هر تغییر باید bottleneck اندازه‌گیری‌شده و هدف عددی داشته باشد؛ تعداد service هدف موفقیت نیست.

## ۶. قرارداد API و backlog پوشش endpointها

همهٔ مسیرهای زیر زیر `/api/v1/` هستند. مسیرهای فعلی را ناگهانی حذف نکنید؛ اگر قرارداد گزارش انتخاب شد alias/deprecation و consumer migration ثبت شود. صحت callback به provider verification وابسته است، نه عمومی یا خصوصی بودن URL.

| دامنه | مسیرهای فعلی نمونه | قرارداد هدف و مرحله |
|---|---|---|
| Auth/profile | `auth/request-code/`, `verify-code/`, `me/`, `logout/` | OTP، profile patch، session revoke در R1؛ register/login password/social فقط مطابق سیاست R0/R11 |
| Catalog | `catalog/products/`, `products/{slug}/`, categories/brands/facets/suggestions | list/detail/by-id/by-slug/variants و collection در R2/R8؛ schema و pagination تثبیت شود |
| Cart/address | `commerce/cart/`, `cart/lines/{id}/`, `addresses/`, `quote/` | CRUD کامل، estimate و delivery selection در R4؛ coupons در R9 |
| Checkout/orders | `commerce/checkout/`, `orders/`, `orders/{id}/` | confirm idempotent، history/detail در R4؛ cancel/tracking/invoice/returns در R6 |
| Payments | فقط `payments/methods/` | initiation/status/verify/webhook، refunds/reconciliation در R5؛ هیچ callback بدون verify credit نسازد |
| Sellers | applications، stores، catalog-variants، offer/profile | onboarding/KYC/products/offers/inventory در R3؛ orders/ship در R6؛ settlements/payout requests در R7 |
| Admin | overview/finance؛ operations sellers/categories/staff/audit | catalog R2، inventory R3، orders R4، transactions/refund R5–R6، commission/payout R7، support/content R8، coupon/report R9 |
| Trust/engagement | مدل و serviceهای اولیه، API کامل ندارد | wishlist/reviews/questions/comparison R8؛ alerts/follow/recommendation R9/R11 |

قواعد مشترک: validation یکسان، stable machine-readable error code، correlation ID، limit/max page size، ownership، rate limiting، timezone مشخص، money unit، timestamp استاندارد و schema errorها. public response اطلاعات تماس/بانک/KYC فروشنده را منتشر نکند. PATCH عمومی status برای سفارش به commandهای transition محدود تبدیل شود.

## ۷. راهبرد کیفیت و مدارک پذیرش

| نوع آزمون | سناریوهای مهم | زمان |
|---|---|---|
| Domain/unit | مجموع مبالغ، rounding، eligibility، transition، commission | هر milestone مربوط |
| PostgreSQL integration | آخرین موجودی، coupon cap، reservation/expiry race، duplicate payment/refund/payout | R3–R7/R9؛ SQLite کافی نیست |
| Contract | OpenAPI، provider sandbox، webhook authentication، carrier mapping | R0 سپس هر adapter |
| Permission | customer/seller isolation و نقش finance/support/admin | تمام endpointهای خصوصی |
| Browser E2E | چند فروشنده → checkout → پرداخت → ارسال → مرجوعی؛ موبایل RTL | R4 به بعد؛ gate R10 |
| Recovery/operations | worker restart، retry، backlog، restore، migration failure، rollback | R1، R5 و R10 |

برای هر پذیرش مسیر `docs/releases/Rn/` شامل commit SHA، محیط، فرمان/سناریو، نتیجه، screenshots مجاز بدون دادهٔ حساس، defectهای باز و sign-off باشد. آزمون پول/موجودی با failure injection انجام شود؛ تست صرفاً بازنویسی implementation نباشد.

## ۸. ریسک‌ها و تصمیم‌های بیرونی

| ریسک/وابستگی | مالک | اقدام و اثر بر برنامه |
|---|---|---|
| قرارداد gateway و finance provider | Business + Payments | از R0 پیگیری؛ sandbox mock فقط برای توسعه؛ نبود درگاه نخست مانع beta تراکنشی |
| SMS، دامنه، storage و hosting | DevOps + Business | تا R1 staging، پیش از R10 production؛ هزینه و SLA ثبت شود |
| tax، invoice، merchant of record | Finance + Legal | تا R0 قاعدهٔ اولیه؛ snapshot/تسویه بر اساس تصمیم مصوب |
| commission/settlement و reserve مرجوعی | Finance | پیش از R7؛ تغییر نرخ قبلی ledger را بازنویسی نکند |
| carrier و fulfillment | Operations | تا R3 سیاست؛ tracking دستی برای beta اگر مصوب، sync واقعی پذیرش جدا |
| catalog و seller واقعی | Product + Operations | آماده‌سازی همزمان R2؛ دادهٔ seed جای pilot را نگیرد |
| concurrency در SQLite پنهان می‌ماند | Tech lead + QA | PostgreSQL در CI/staging و race tests قبل از پول واقعی |
| گستردگی گزارش | Product | launch scope صریح؛ R11/R12 بسته‌های جدا؛ تغییر دامنه به برآورد بازتاب داده شود |

## ۹. مدیریت کار و Definition of Done

- هر Rn یک epic؛ storyها بر اساس جریان عمودی باشند: API + UI + admin + permissions + آزمون، نه فقط «ساخت مدل».
- هر story: actor، trigger، happy/failure path، acceptance، dependency، priority، owner، estimate، migration/API impact و evidence link.
- PRهای کوچک و branch مستقل؛ main قابل build؛ code/migration/config/docs مربوط کنار هم؛ credentials وارد Git نشوند.
- پذیرش milestone فقط بعد از merge، گذر CI، demo روی staging، بستهٔ شواهد و رفع blockerهای همان دامنه؛ سپس push/tag طبق قواعد `MILESTONES.md`. این سند تغییری push یا tag نمی‌کند.
- مرور هفتگی: milestone progress بر اساس story پذیرفته‌شده، blocker، پرداخت/موجودی defects، تغییر برآورد و تصمیم‌های لازم؛ درصد خط کد معیار پیشرفت نیست.

## ۱۰. backlog آغاز اجرا

| شناسهٔ پیشنهادی | کار | اولویت | مالک |
|---|---|---|---|
| R0-01 | اجرای baseline تمیز روی Compose/PostgreSQL و ثبت اختلاف با README | P0 | Tech lead + QA |
| R0-02 | traceability همهٔ قابلیت‌های گزارش به R0–R12 و تأیید دامنهٔ launch | P0 | Product |
| R0-03 | ADR Offer/Inventory/Reservation/SellerOrder/ReturnLine و برنامهٔ migration | P0 | Backend |
| R0-04 | OpenAPI و mapping مسیرهای فعلی/هدف، state/permission matrix | P0 | Backend + Frontend |
| R0-05 | قواعد tax/commission/cancel/return و مثال مالی دو فروشنده | P0 | Finance + Product |
| R0-06 | اخذ مدارک و sandbox درگاه اول، SMS و carrier | P0 | Business |
| R0-07 | wireframe checkout، seller fulfillment، refund admin و error states RTL | P1 | Design + Frontend |
| R1-01 | CI: PostgreSQL tests، migration check، typecheck، build | P0 | DevOps |
| R1-02 | seed سناریوی دو فروشنده و دادهٔ pilot غیرحساس | P1 | Backend + QA |
| R1-03 | staging، secrets، SMS adapter و گزارش سلامت queue/scheduler | P0 | DevOps + Backend |

کار بعدی پس از این برنامه R0-01 است؛ تکمیل baseline و تصمیم‌های R0 باید پیش از اعلام deadline قطعی انجام شود.
