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
          <span className="eyebrow">خرید از فروشندگان مختلف</span>
          <h1 id="page-title">تجربه‌ای ساده‌تر برای خرید از فروشندگان مختلف</h1>
          <p>محصولات را جست‌وجو کنید، قیمت و شرایط فروشندگان را ببینید و سفارش‌های خود را از حساب کاربری پیگیری کنید.</p>
          <a className="catalog-link" href="/products/">مشاهدهٔ محصولات</a>
          <a className="catalog-link" href="/collections/">مجموعه‌های منتخب</a>
          <div className="feature-list" aria-label="بخش‌های فروشگاه">
            <span>مقایسهٔ پیشنهادها</span>
            <span>پیگیری سفارش</span>
            <span>پنل فروشندگان</span>
          </div>
        </section>
      </main>
    </>
  );
}
