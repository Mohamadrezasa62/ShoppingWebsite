"use client";
import { usePathname } from "next/navigation";
import { useRef, type ReactNode } from "react";
import { Brand } from "./brand";
import { UiIcon, type IconName } from "./ui-icon";
import { PromoBanner, type BannerKind } from "./promo-banner";
const primary: { href: string; title: string; icon: IconName }[] = [
  { href: "/", title: "خانه", icon: "home" }, { href: "/products/", title: "محصولات", icon: "grid" },
  { href: "/collections/", title: "مجموعه‌ها", icon: "box" }, { href: "/compare/", title: "مقایسه", icon: "compare" },
  { href: "/wishlist/", title: "علاقه‌مندی‌ها", icon: "heart" }, { href: "/orders/", title: "سفارش‌ها", icon: "bag" },
  { href: "/support/", title: "پشتیبانی", icon: "support" }, { href: "/account/", title: "حساب من", icon: "user" },
];
const secondary = [["/following/", "دنبال‌شده‌ها"], ["/alerts/", "اعلان محصول"], ["/recently-viewed/", "اخیراً دیده‌شده‌ها"], ["/my-reviews/", "نظرات و تصاویر من"], ["/seller-reviews/", "امتیازهای فروشندگان"], ["/returns/", "مرجوعی‌ها"], ["/cancellations/", "لغو ارسال"], ["/disputes/", "اختلاف‌های سفارش"], ["/notifications/", "اعلان‌ها"], ["/content/", "راهنماها و قوانین"], ["/seller-panel/", "پنل فروشنده"], ["/admin-panel/", "پنل مدیریت"]];
export function AppShell({ children }: { children: ReactNode }) {
  const path = usePathname() ?? "/";
  const dialog = useRef<HTMLDialogElement>(null);
  const isHome = path === "/", isLogin = path.startsWith("/login");
  const banner: BannerKind = /seller-panel|admin-panel/.test(path) ? "seller" : /support|content|disputes/.test(path) ? "support" : /orders|returns|cancellations|account|notifications/.test(path) ? "orders" : "choice";
  const active = (href: string) => href === "/" ? isHome : path.startsWith(href);
  return <div className={`gz-app ${isLogin ? "gz-auth-shell" : ""}`}>
    <a className="gz-skip" href="#page-content">رفتن به محتوای اصلی</a>
    <nav className="gz-rail" aria-label="ناوبری اصلی"><Brand compact /><div>{primary.map(item => <a key={item.href} href={item.href} aria-label={item.title} title={item.title} aria-current={active(item.href) ? "page" : undefined}><UiIcon name={item.icon} /><span>{item.title}</span></a>)}</div><span className="gz-rail-caption">انتخابِ تو</span></nav>
    <div className="gz-workspace"><header className="gz-topbar"><Brand /><form className="gz-search" action="/products/" role="search"><UiIcon name="search" /><input type="search" name="q" aria-label="جست‌وجو در گزیناو" placeholder="دنبال چه می‌گردی؟" /><button type="submit" aria-label="جست‌وجو"><UiIcon name="arrow" /></button></form><div className="gz-top-actions"><a className="gz-icon-button" href="/notifications/" aria-label="اعلان‌ها"><UiIcon name="bell" /></a><a className="gz-icon-button" href="/cart/" aria-label="سبد خرید"><UiIcon name="bag" /></a><a className="gz-account-button" href="/account/" aria-label="حساب من"><UiIcon name="user" /><span>حساب من</span></a><button className="gz-icon-button gz-menu-button" aria-label="بازکردن منوی همهٔ بخش‌ها" onClick={() => dialog.current?.showModal()}><UiIcon name="menu" /></button></div></header>
    <div className="gz-subnav"><span>خرید با دید باز.</span><nav aria-label="دسترسی سریع"><a href="/products/">کشف محصولات</a><a href="/collections/">مجموعه‌های منتخب</a><a href="/seller-panel/">فروشنده شوید</a></nav><button className="gz-text-button" onClick={() => dialog.current?.showModal()}>همهٔ بخش‌ها <UiIcon name="menu" /></button></div>
    {!isHome && !isLogin && <div className="gz-context-banner"><PromoBanner kind={banner} compact /></div>}
    <div id="page-content" tabIndex={-1} className="gz-content">{children}</div>
    <footer className="gz-footer"><Brand /><p>انتخاب روشن. خرید مطمئن.</p><nav aria-label="پیوندهای پایانی"><a href="/content/">راهنماها و قوانین</a><a href="/support/">پشتیبانی</a><a href="/seller-panel/">همکاری با فروشندگان</a></nav><small>گزیناو · بازارگاه انتخاب‌های تو</small></footer></div>
    <nav className="gz-mobile-nav" aria-label="ناوبری موبایل">{[primary[0], primary[1], { href: "/cart/", title: "سبد", icon: "bag" as const }, primary[7]].map(item => <a key={item.href} href={item.href} aria-current={active(item.href) ? "page" : undefined}><UiIcon name={item.icon} /><span>{item.title}</span></a>)}<button onClick={() => dialog.current?.showModal()}><UiIcon name="menu" /><span>بیشتر</span></button></nav>
    <dialog ref={dialog} className="gz-navigation-dialog" onClick={event => { if (event.target === event.currentTarget) dialog.current?.close(); }}><header><Brand /><button className="gz-icon-button" onClick={() => dialog.current?.close()} aria-label="بستن منو"><UiIcon name="close" /></button></header><h2>همهٔ بخش‌های گزیناو</h2><nav aria-label="همهٔ بخش‌ها">{[...primary.map(x => [x.href, x.title]), ...secondary].map(([href, title]) => <a key={href} href={href}>{title}<UiIcon name="arrow" /></a>)}</nav><a className="gz-button" href="/login/">ورود / ثبت‌نام</a></dialog>
  </div>;
}
