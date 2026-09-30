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
          <span className="eyebrow">بازارگاه در حال توسعه</span>
          <h1 id="page-title">تجربه‌ای ساده‌تر برای خرید از فروشندگان مختلف</h1>
          <p>محصولات منتشرشده را جست‌وجو کنید و پیشنهاد فروشندگان را ببینید. خرید و پرداخت در مراحل بعدی اضافه می‌شود.</p>
          <a className="catalog-link" href="/products/">مشاهدهٔ محصولات</a>
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
