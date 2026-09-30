"use client";

import { useEffect, useState } from "react";
import { apiRequest } from "@/lib/api";

type Line = { id: number; product_title: string; product_slug: string; variant: Record<string, string>; seller: string; quantity: number; unit_price_toman: number; line_total_toman: number; free_stock: number; available: boolean };
type Cart = { lines: Line[]; estimated_subtotal_toman: number; can_checkout: boolean; shipping_and_fees_calculated: boolean };

export default function CartPage() {
  const [cart, setCart] = useState<Cart | null>(null);
  const [error, setError] = useState("");
  const [signedOut, setSignedOut] = useState(false);
  async function load() {
    try {
      const response = await fetch("/api/v1/commerce/cart/", { credentials: "same-origin" });
      if (response.status === 401) { setSignedOut(true); return; }
      if (!response.ok) throw new Error();
      setCart((await response.json()).cart);
    } catch { setError("سبد خرید بارگذاری نشد."); }
  }
  useEffect(() => { void load(); }, []);
  async function change(lineId: number, quantity: number) {
    setError("");
    const response = await apiRequest("PATCH", `/api/v1/commerce/cart/lines/${lineId}/`, { quantity });
    if (response.ok) setCart((await response.json()).cart);
    else setError("تغییر تعداد انجام نشد. موجودی را بررسی کنید.");
  }
  async function remove(lineId: number) {
    setError("");
    const response = await apiRequest("DELETE", `/api/v1/commerce/cart/lines/${lineId}/`);
    if (response.ok) setCart((await response.json()).cart);
    else setError("حذف کالا انجام نشد.");
  }
  return <div className="catalog-shell"><header className="site-header"><div className="header-inner"><a className="brand" href="/">ShoppingWebsite</a><a href="/products/">محصولات</a></div></header><main className="catalog-main"><h1>سبد خرید</h1>
    {error && <p role="alert">{error}</p>}{signedOut ? <p>برای دیدن سبد خرید <a href="/login/">وارد شوید</a>.</p> : !cart ? <p>در حال بارگذاری...</p> : cart.lines.length === 0 ? <p>سبد خرید خالی است. <a href="/products/">محصولات را ببینید</a>.</p> : <><ul className="admin-list">{cart.lines.map((line) => <li className="cart-line" key={line.id}><div><a href={`/products/${encodeURIComponent(line.product_slug)}/`}><strong>{line.product_title}</strong></a><p>{Object.entries(line.variant).map(([key, value]) => `${key}: ${value}`).join(" · ")} · {line.seller}</p><p>قیمت واحد: {line.unit_price_toman.toLocaleString("fa-IR")} تومان</p>{!line.available && <p className="cart-warning">موجودی یا وضعیت این پیشنهاد تغییر کرده است.</p>}</div><div><b>{line.line_total_toman.toLocaleString("fa-IR")} تومان</b><div className="cart-actions"><label>تعداد<select value={line.quantity} onChange={(event) => void change(line.id, Number(event.target.value))}>{Array.from({ length: Math.min(100, Math.max(line.quantity, line.free_stock)) }, (_, index) => index + 1).map((number) => <option key={number} value={number}>{number}</option>)}</select></label><button type="button" onClick={() => void remove(line.id)}>حذف</button></div></div></li>)}</ul><section className="admin-card"><h2>برآورد سبد خرید</h2><p>جمع کالاها: <strong>{cart.estimated_subtotal_toman.toLocaleString("fa-IR")} تومان</strong></p><p>هزینهٔ ارسال، تخفیف و مبلغ نهایی هنوز محاسبه نشده‌اند.</p>{!cart.can_checkout && <p className="cart-warning">برای ادامه، کالاهای ناموجود را اصلاح یا حذف کنید.</p>}<button type="button" className="catalog-action" disabled>ادامهٔ خرید به‌زودی</button></section></>}
  </main></div>;
}
