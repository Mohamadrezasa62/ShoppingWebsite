"use client";

import { useCallback, useEffect, useState } from "react";
import { apiRequest } from "@/lib/api";

type Follow = { id: number; kind: string; name: string };
type Product = { id: number; title: string; slug: string; price_toman: number };

export default function FollowingPage() {
  const [following, setFollowing] = useState<Follow[]>([]);
  const [products, setProducts] = useState<Product[]>([]);
  const [notice, setNotice] = useState("");
  const [busy, setBusy] = useState(false);
  const load = useCallback(async () => {
    try {
      const responses = await Promise.all([fetch("/api/v1/catalog/following/", { credentials: "same-origin" }), fetch("/api/v1/catalog/feed/", { credentials: "same-origin" })]);
      if (responses.some((response) => !response.ok)) throw new Error();
      const [follows, feed] = await Promise.all(responses.map((response) => response.json()));
      setFollowing(follows.following); setProducts(feed.products);
    } catch { setNotice("برای مشاهدهٔ دنبال‌شده‌ها وارد حساب شوید؛ اگر وارد هستید دوباره تلاش کنید."); }
  }, []);
  useEffect(() => { void load(); }, [load]);
  async function remove(id: number) {
    setBusy(true); setNotice("");
    try {
      const response = await apiRequest("DELETE", `/api/v1/catalog/following/${id}/`);
      if (!response.ok) throw new Error();
      await load();
    } catch { setNotice("لغو دنبال‌کردن انجام نشد."); } finally { setBusy(false); }
  }
  return <main className="catalog-main"><a href="/account/">حساب کاربری</a><h1>برندها و فروشندگان دنبال‌شده</h1><p>از صفحهٔ محصول برند یا فروشنده را دنبال کنید. محصولات موجود آن‌ها در این صفحه نمایش داده می‌شوند. دنبال‌کردن باعث ارسال پیام بازاریابی نمی‌شود.</p>
    {notice && <p role="status">{notice}</p>}
    <ul className="admin-list">{following.map((row) => <li className="admin-record" key={row.id}><span>{row.kind === "brand" ? "برند" : "فروشنده"} · {row.name}</span><button disabled={busy} onClick={() => void remove(row.id)}>لغو دنبال‌کردن</button></li>)}</ul>
    {following.length === 0 && <p>هنوز برندی یا فروشنده‌ای دنبال نکرده‌اید.</p>}
    <h2>محصولات موجود دنبال‌شده‌ها</h2><ul className="admin-list">{products.map((row) => <li className="admin-record" key={row.id}><a href={`/products/${encodeURIComponent(row.slug)}/`}>{row.title}</a><span>از {row.price_toman.toLocaleString("fa-IR")} تومان</span></li>)}</ul>
    {products.length === 0 && <p>فعلاً محصول موجودی برای نمایش نیست.</p>}<a href="/products/">دیدن محصولات</a>
  </main>;
}
