export default function Home() {
  return (
    <>
      <header className="site-header">
        <div className="header-inner">
          <strong className="brand">ShoppingWebsite</strong>
          <a href="/login" className="header-note">ورود / ثبت‌نام</a>
        </div>
      </header>
      <main className="main-content">
        <section className="intro-card" aria-labelledby="page-title">
          <span className="eyebrow">در حال توسعه</span>
          <h1 id="page-title">تجربه‌ای ساده‌تر برای خرید از فروشندگان مختلف</h1>
          <p>زیرساخت بازارگاه در حال ساخت است. جست‌وجو، مقایسهٔ فروشندگان و خرید امن در مراحل بعدی اضافه می‌شود.</p>
          <div className="feature-list" aria-label="بخش‌های برنامه‌ریزی‌شده">
            <span>مقایسهٔ پیشنهادها</span>
            <span>پیگیری سفارش</span>
            <span>پنل فروشندگان</span>
          </div>
        </section>
      </main>
    </>
  );
}
