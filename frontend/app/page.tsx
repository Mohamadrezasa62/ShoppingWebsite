import { PromoBanner } from "@/components/promo-banner";
import { BrandMark } from "@/components/brand";
import { UiIcon } from "@/components/ui-icon";

export default function Home() {
  return <main className="gz-home">
    <div className="gz-page-heading"><div><span className="gz-kicker">برای انتخاب‌های هر روز تو</span><h1>سلام، به گزیناو خوش آمدی.</h1></div><a className="gz-text-link" href="/products/">کشف همهٔ محصولات <UiIcon name="arrow" /></a></div>
    <div className="gz-hero-grid"><section className="gz-hero" aria-labelledby="home-title"><div><span className="gz-kicker"><span className="gz-live-dot" /> فضایی برای انتخاب بهتر</span><h2 id="home-title">انتخاب روشن.<br /><span>خرید مطمئن.</span></h2><p>بین پیشنهادهای مختلف، انتخابی پیدا کن که واقعاً به تو می‌خورد. قیمت و شرایط فروشندگان را ببین، مقایسه کن و با دید باز تصمیم بگیر.</p><div className="gz-hero-actions"><a className="gz-button" href="/products/">شروع کشف محصولات <UiIcon name="arrow" /></a><a className="gz-text-link" href="/content/">گزیناو چطور کار می‌کند؟</a></div></div><div className="gz-brand-sculpture"><BrandMark /><span>GOZINAV</span><small>انتخاب، به سبک تو.</small></div></section><aside className="gz-discovery-card"><div><span className="gz-kicker">کمتر سردرگم شو.</span><h2>بیشتر<br />مقایسه کن.</h2><p>تفاوت مشخصات، قیمت و شرایط را کنار هم ببین.</p></div><div className="gz-comparison-art" aria-hidden="true"><div><i /><i /><i /><i /></div><div><i /><i /><i /><i /></div><span><UiIcon name="compare" /></span></div><a className="gz-text-link" href="/compare/">مقایسهٔ محصولات <UiIcon name="arrow" /></a></aside></div>
    <section className="gz-value-grid" aria-label="مزیت‌های خرید از گزیناو">{[
      { icon: "compare" as const, title: "چند فروشنده، یک نگاه", text: "پیشنهادها و شرایط فروشندگان را در صفحهٔ هر کالا کنار هم ببین.", link: "/products/", tone: "gz-lilac" },
      { icon: "box" as const, title: "مسیر خرید، یکپارچه", text: "سفارش‌ها، جزئیات ارسال و درخواست‌ها را در حساب خودت پیگیری کن.", link: "/orders/", tone: "gz-blue" },
      { icon: "support" as const, title: "گفت‌وگو، بدون سردرگمی", text: "درخواست پشتیبانی را ثبت کن و پاسخ‌ها را در همان گفت‌وگو دنبال کن.", link: "/support/", tone: "gz-sand" },
    ].map((item, index) => <a key={item.title} className={`gz-value-card ${item.tone}`} href={item.link}><div className="gz-value-top"><UiIcon name={item.icon} /><span>{(index + 1).toLocaleString("fa-IR", { minimumIntegerDigits: 2 })}</span></div><h3>{item.title}</h3><p>{item.text}</p><UiIcon name="arrow" /></a>)}</section>
    <section className="gz-explore"><div className="gz-section-heading"><div><span className="gz-kicker">راه‌های ساده‌تر برای کشف</span><h2>انتخاب بعدی‌ات را پیدا کن.</h2></div><a className="gz-text-link" href="/products/">همهٔ محصولات <UiIcon name="arrow" /></a></div><div className="gz-explore-grid">{[
      { title: "مجموعه‌های منتخب", text: "چند انتخاب با یک نگاه مشترک.", href: "/collections/", icon: "grid" as const },
      { title: "علاقه‌مندی‌های تو", text: "انتخاب‌های بعدی را اینجا نگه دار.", href: "/wishlist/", icon: "heart" as const },
      { title: "دنبال‌شده‌ها", text: "به‌روز از برندها و فروشندگان مورد علاقه.", href: "/following/", icon: "bell" as const },
      { title: "اخیراً دیده‌شده‌ها", text: "به انتخاب‌هایی که دیده‌ای برگرد.", href: "/recently-viewed/", icon: "book" as const },
    ].map(item => <a key={item.href} href={item.href}><UiIcon name={item.icon} /><h3>{item.title}</h3><p>{item.text}</p><UiIcon name="arrow" /></a>)}</div></section>
    <PromoBanner kind="seller" /><div className="gz-home-help"><p>هنوز سؤالی داری؟ راهنمایی‌ات می‌کنیم.</p><a className="gz-text-link" href="/support/">گفت‌وگو با پشتیبانی <UiIcon name="arrow" /></a></div>
  </main>;
}