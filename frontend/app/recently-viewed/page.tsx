"use client";
import { useCallback, useEffect, useState } from "react";
import { apiRequest } from "@/lib/api";

type Product = { id: number; title: string; slug: string; price_toman: number; viewed_at: string };
type History = { enabled: boolean; retention_days: number; limit: number; products: Product[] };

export default function RecentlyViewedPage() {
  const [history, setHistory] = useState<History | null>(null);
  const [notice, setNotice] = useState("");
  const [busy, setBusy] = useState(false);
  const load = useCallback(async () => {
    const response = await fetch("/api/v1/catalog/history/", { credentials: "same-origin", cache: "no-store" });
    if (!response.ok) throw new Error();
    setHistory(await response.json());
  }, []);
  useEffect(() => { void load().catch(() => setNotice("برای مشاهدهٔ سابقه وارد حساب شوید؛ اگر وارد هستید دوباره تلاش کنید.")); }, [load]);
  async function change(method: "PATCH" | "DELETE", enabled?: boolean) {
    setBusy(true); setNotice("");
    try {
      const response = await apiRequest(method, "/api/v1/catalog/history/", method === "PATCH" ? { enabled } : undefined);
      if (!response.ok) throw new Error();
      setHistory(await response.json());
      setNotice(method === "DELETE" ? "سابقه پاک شد؛ تنظیم فعال‌سازی حفظ شده است." : enabled ? "ثبت سابقهٔ بازدیدهای بعدی فعال شد." : "ثبت سابقه غیرفعال و سابقهٔ قبلی پاک شد.");
    } catch { setNotice("تغییر انجام نشد؛ دوباره تلاش کنید."); } finally { setBusy(false); }
  }
  return <main className="catalog-main"><a href="/account/">حساب کاربری</a><h1>اخیراً دیده‌شده‌ها</h1>
    <p>با انتخاب شما، حداکثر ۵۰ محصول دیده‌شده در ۳۰ روز اخیر برای همین حساب نگهداری می‌شود. سابقه پیش‌فرض غیرفعال است. این انتخاب اجازهٔ ارسال پیام بازاریابی نمی‌دهد.</p>
    {notice && <p role="status">{notice}</p>}{history && <><label><input type="checkbox" checked={history.enabled} disabled={busy} onChange={(event) => void change("PATCH", event.target.checked)} /> نگهداری سابقهٔ بازدید برای حساب من</label><p>غیرفعال‌کردن، سابقهٔ قبلی را هم پاک می‌کند. محصولات مخفی یا ناموجود در این فهرست نمایش داده نمی‌شوند.</p>
      <button disabled={busy || !history.products.length} onClick={() => void change("DELETE")}>پاک‌کردن سابقه</button><button disabled={busy} onClick={() => void load().catch(() => setNotice("فهرست دریافت نشد."))}>به‌روزرسانی فهرست</button>
      <ul className="admin-list">{history.products.map((product) => <li className="admin-record" key={product.id}><a href={`/products/${encodeURIComponent(product.slug)}/`}>{product.title}</a><span>از {product.price_toman.toLocaleString("fa-IR")} تومان · {new Date(product.viewed_at).toLocaleDateString("fa-IR")}</span></li>)}</ul>{!history.products.length && <p>محصولی برای نمایش ثبت نشده است.</p>}</>}
  </main>;
}
