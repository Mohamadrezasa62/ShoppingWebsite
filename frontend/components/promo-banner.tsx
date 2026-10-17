import { BrandMark } from "./brand";
import { UiIcon } from "./ui-icon";
const messages = {
  choice: { eyebrow: "انتخاب آگاهانه، از همین‌جا", title: "یک کالا. چند انتخاب.", text: "قیمت و شرایط فروشندگان را کنار هم ببین و انتخاب خودت را بساز.", cta: "شروع مقایسه", href: "/compare/", tone: "blue" },
  orders: { eyebrow: "مسیر خرید، روشن و یکپارچه", title: "از انتخاب تا دریافت، کنارت هستیم.", text: "سفارش، وضعیت ارسال و گفت‌وگو با پشتیبانی را در یک جا دنبال کن.", cta: "سفارش‌های من", href: "/orders/", tone: "lilac" },
  seller: { eyebrow: "گزیناو برای فروشندگان", title: "فروشگاه تو، فرصت‌های بیشتر.", text: "پیشنهادها، موجودی و سفارش‌های فروشگاهت را یکپارچه مدیریت کن.", cta: "ورود به پنل فروشنده", href: "/seller-panel/", tone: "dark" },
  support: { eyebrow: "وقتی به راهنمایی نیاز داری", title: "پاسخ روشن، انتخاب مطمئن‌تر.", text: "راهنماها را بخوان یا درخواستت را در گفت‌وگو با پشتیبانی پیگیری کن.", cta: "مرکز راهنما", href: "/content/", tone: "sand" },
} as const;
export type BannerKind = keyof typeof messages;
export function PromoBanner({ kind = "choice", compact = false }: { kind?: BannerKind; compact?: boolean }) {
  const item = messages[kind];
  return <aside className={`gz-promo gz-${item.tone} ${compact ? "gz-promo-compact" : ""}`} aria-label={item.eyebrow}><div className="gz-promo-copy"><span className="gz-kicker">{item.eyebrow}</span><h2>{item.title}</h2><p>{item.text}</p><a className="gz-button" href={item.href}>{item.cta}<UiIcon name="arrow" /></a></div><BrandMark className="gz-promo-mark" /></aside>;
}
