"use client";

import { useEffect, useState } from "react";
import { apiRequest } from "@/lib/api";

type Line = { id: number; product_title: string; product_slug: string; variant: Record<string, string>; seller: string; quantity: number; unit_price_toman: number; line_total_toman: number; free_stock: number; available: boolean };
type Cart = { lines: Line[]; estimated_subtotal_toman: number; can_checkout: boolean; shipping_and_fees_calculated: boolean };
type Address = { id: number; full_name: string; phone: string; province: string; city: string; street: string; postal_code: string };
type Quote = { shipping_total_toman: number | null; estimated_total_toman: number | null; ready: boolean; deliveries: { seller: string; fee_toman: number; min_days: number; max_days: number }[]; missing_shipping_rules: { seller_id: number }[] };

export default function CartPage() {
  const [cart, setCart] = useState<Cart | null>(null);
  const [error, setError] = useState("");
  const [signedOut, setSignedOut] = useState(false);
  const [addresses, setAddresses] = useState<Address[]>([]);
  const [selectedAddressId, setSelectedAddressId] = useState("");
  const [quote, setQuote] = useState<Quote | null>(null);
  const [fullName, setFullName] = useState("");
  const [phone, setPhone] = useState("");
  const [province, setProvince] = useState("");
  const [city, setCity] = useState("");
  const [street, setStreet] = useState("");
  const [postalCode, setPostalCode] = useState("");
  async function load() {
    try {
      const response = await fetch("/api/v1/commerce/cart/", { credentials: "same-origin" });
      if (response.status === 401) { setSignedOut(true); return; }
      if (!response.ok) throw new Error();
      setCart((await response.json()).cart);
    } catch { setError("سبد خرید بارگذاری نشد."); }
  }
  useEffect(() => { void load(); }, []);
  useEffect(() => {
    fetch("/api/v1/commerce/addresses/", { credentials: "same-origin" }).then((response) => response.json())
      .then((data) => { if (data.addresses) { setAddresses(data.addresses); setSelectedAddressId(data.addresses[0]?.id.toString() ?? ""); } })
      .catch(() => setError("نشانی‌ها بارگذاری نشدند."));
  }, []);
  useEffect(() => {
    if (!selectedAddressId || !cart?.lines.length) { setQuote(null); return; }
    fetch(`/api/v1/commerce/quote/?address_id=${selectedAddressId}`, { credentials: "same-origin" })
      .then((response) => response.json()).then((data) => setQuote(data.quote ?? null))
      .catch(() => setQuote(null));
  }, [selectedAddressId, cart]);
  async function addAddress(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault(); setError("");
    const response = await apiRequest("POST", "/api/v1/commerce/addresses/", { full_name: fullName, phone, province, city, street, postal_code: postalCode });
    if (response.ok) { const address = (await response.json()).address as Address; setAddresses([address, ...addresses]); setSelectedAddressId(String(address.id)); setFullName(""); setPhone(""); setProvince(""); setCity(""); setStreet(""); setPostalCode(""); }
    else setError("نشانی ثبت نشد. شمارهٔ همراه و کدپستی را بررسی کنید.");
  }
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
    {error && <p role="alert">{error}</p>}{signedOut ? <p>برای دیدن سبد خرید <a href="/login/">وارد شوید</a>.</p> : !cart ? <p>در حال بارگذاری...</p> : cart.lines.length === 0 ? <p>سبد خرید خالی است. <a href="/products/">محصولات را ببینید</a>.</p> : <><ul className="admin-list">{cart.lines.map((line) => <li className="cart-line" key={line.id}><div><a href={`/products/${encodeURIComponent(line.product_slug)}/`}><strong>{line.product_title}</strong></a><p>{Object.entries(line.variant).map(([key, value]) => `${key}: ${value}`).join(" · ")} · {line.seller}</p><p>قیمت واحد: {line.unit_price_toman.toLocaleString("fa-IR")} تومان</p>{!line.available && <p className="cart-warning">موجودی یا وضعیت این پیشنهاد تغییر کرده است.</p>}</div><div><b>{line.line_total_toman.toLocaleString("fa-IR")} تومان</b><div className="cart-actions"><label>تعداد<select value={line.quantity} onChange={(event) => void change(line.id, Number(event.target.value))}>{Array.from({ length: Math.min(100, Math.max(line.quantity, line.free_stock)) }, (_, index) => index + 1).map((number) => <option key={number} value={number}>{number}</option>)}</select></label><button type="button" onClick={() => void remove(line.id)}>حذف</button></div></div></li>)}</ul><section className="admin-card"><h2>نشانی تحویل</h2><label>نشانی ذخیره‌شده<select value={selectedAddressId} onChange={(event) => setSelectedAddressId(event.target.value)}><option value="">انتخاب نشانی</option>{addresses.map((address) => <option key={address.id} value={address.id}>{address.province}، {address.city}، {address.street}</option>)}</select></label><form className="admin-inline-form" onSubmit={addAddress}><label>نام گیرنده<input required value={fullName} onChange={(event) => setFullName(event.target.value)} /></label><label>شمارهٔ همراه<input required inputMode="tel" value={phone} onChange={(event) => setPhone(event.target.value)} /></label><label>استان<input required value={province} onChange={(event) => setProvince(event.target.value)} /></label><label>شهر<input required value={city} onChange={(event) => setCity(event.target.value)} /></label><label>نشانی<input required value={street} onChange={(event) => setStreet(event.target.value)} /></label><label>کد پستی<input required inputMode="numeric" value={postalCode} onChange={(event) => setPostalCode(event.target.value)} /></label><button type="submit">افزودن نشانی</button></form></section><section className="admin-card seller-section"><h2>برآورد سبد خرید</h2><p>جمع کالاها: <strong>{cart.estimated_subtotal_toman.toLocaleString("fa-IR")} تومان</strong></p>{quote?.ready ? <><p>هزینهٔ ارسال: {quote.shipping_total_toman?.toLocaleString("fa-IR")} تومان</p><p><strong>برآورد کل: {quote.estimated_total_toman?.toLocaleString("fa-IR")} تومان</strong></p><ul>{quote.deliveries.map((delivery, index) => <li key={index}>{delivery.seller}: {delivery.min_days} تا {delivery.max_days} روز · {delivery.fee_toman.toLocaleString("fa-IR")} تومان</li>)}</ul></> : <p>برای برآورد ارسال، نشانی معتبر و قوانین ارسال لازم است.</p>}<p>این برآورد نهایی نیست؛ تخفیف‌ها و مبلغ قطعی در مرحلهٔ ثبت سفارش محاسبه می‌شوند.</p>{!cart.can_checkout && <p className="cart-warning">برای ادامه، کالاهای ناموجود را اصلاح یا حذف کنید.</p>}<button type="button" className="catalog-action" disabled>ادامهٔ خرید به‌زودی</button></section></>}
  </main></div>;
}
