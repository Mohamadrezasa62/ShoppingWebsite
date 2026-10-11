"use client";
import { useEffect, useState } from "react";
import { apiRequest } from "@/lib/api";
type Item = { product_id: number; title: string; slug: string; available: boolean };
export default function WishlistPage() {
  const [items, setItems] = useState<Item[]>([]);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  async function load() {
    try {
      const response = await fetch("/api/v1/catalog/wishlist/");
      if (!response.ok) { setError(response.status === 401 ? "برای مشاهدهٔ علاقه‌مندی‌ها وارد شوید." : "دریافت اطلاعات انجام نشد."); return; }
      setItems((await response.json()).items);
    } catch { setError("ارتباط برقرار نشد."); } finally { setLoading(false); }
  }
  useEffect(() => { void load(); }, []);
  async function remove(id: number) {
    setBusy(true);
    try {
      const response = await apiRequest("DELETE", `/api/v1/catalog/wishlist/${id}/`);
      if (!response.ok) throw new Error();
      await load();
    } catch { setError("حذف انجام نشد."); } finally { setBusy(false); }
  }
  return <main className="catalog-main"><a href="/account/">حساب من</a><h1>علاقه‌مندی‌ها</h1>{error && <p role="alert">{error} <a href="/login/">ورود</a></p>}{loading ? <p>در حال بارگذاری...</p> : <><ul className="admin-list">{items.map((item) => <li className="admin-record" key={item.product_id}><a href={`/products/${encodeURIComponent(item.slug)}/`}>{item.title}</a>{!item.available && <span>در دسترس نیست</span>}<button disabled={busy} onClick={() => void remove(item.product_id)}>حذف</button></li>)}</ul>{!items.length && !error && <p>فهرست شما خالی است.</p>}</>}</main>;
}
