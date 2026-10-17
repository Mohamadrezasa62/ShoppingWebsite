"use client";

import { useEffect, useState } from "react";
import { apiRequest } from "@/lib/api";
import { CartCoupon } from "@/components/cart-coupon";
import { CheckoutAction } from "@/components/checkout-action";

type Line = { seller_id: number; fulfillment: string; id: number; product_title: string; product_slug: string; variant: Record<string, string>; seller: string; quantity: number; unit_price_toman: number; line_total_toman: number; free_stock: number; available: boolean };
type Cart = { coupon_code: string; lines: Line[]; estimated_subtotal_toman: number; can_checkout: boolean; shipping_and_fees_calculated: boolean };
type Address = { id: number; full_name: string; phone: string; province: string; city: string; street: string; postal_code: string };
type Quote = { tax_total_toman: number; item_subtotal_toman: number; lines: { id: number; product_title: string; seller: string; quantity: number; unit_price_toman: number; line_total_toman: number; warranty: string; tax: {label: string; rate_bps: number; amount_toman: number} }[]; approval_token: string | null; discount_total_toman: number; coupon_error: string | null; shipping_total_toman: number | null; estimated_total_toman: number | null; ready: boolean; deliveries: { window: { id: number; starts_at: string; ends_at: string } | null; windows: { id: number; starts_at: string; ends_at: string; remaining: number }[]; group_key: string; id: number; label: string; options: { id: number; label: string; fee_toman: number; min_days: number; max_days: number }[]; seller: string; fee_toman: number; min_days: number; max_days: number }[]; missing_shipping_rules: { seller_id: number }[] };

export default function CartPage() {
  const [cart, setCart] = useState<Cart | null>(null);
  const [error, setError] = useState("");
  const [signedOut, setSignedOut] = useState(false);
  const [addresses, setAddresses] = useState<Address[]>([]);
  const [selectedAddressId, setSelectedAddressId] = useState("");
  const [shippingSlots, setShippingSlots] = useState<Record<string, number>>({});
  const [shippingMethods, setShippingMethods] = useState<Record<string, number>>({});
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
    const keys = new Set(cart?.lines.map((line) => `${line.seller_id}:${line.fulfillment}`) ?? []);
    setShippingSlots((previous) => { const next = Object.fromEntries(Object.entries(previous).filter(([key]) => keys.has(key))); return Object.keys(next).length === Object.keys(previous).length ? previous : next; });
    setShippingMethods((previous) => { const next = Object.fromEntries(Object.entries(previous).filter(([key]) => keys.has(key))); return Object.keys(next).length === Object.keys(previous).length ? previous : next; });
  }, [cart]);
  useEffect(() => {
    setQuote(null);
    if (!selectedAddressId || !cart?.lines.length) return;
    const controller = new AbortController();
    fetch(`/api/v1/commerce/quote/?address_id=${selectedAddressId}&shipping_methods=${encodeURIComponent(JSON.stringify(shippingMethods))}&shipping_slots=${encodeURIComponent(JSON.stringify(shippingSlots))}`, { credentials: "same-origin", signal: controller.signal })
      .then((response) => response.json()).then((data) => { if (!controller.signal.aborted) { setQuote(data.quote ?? null); if (data.error === "shipping_method_unavailable") { setShippingMethods({}); setShippingSlots({}); setError("روش ارسال انتخابی دیگر فعال نیست؛ روش و برآورد تازه را بررسی کنید."); } if (data.error === "shipping_slot_unavailable") { setShippingSlots({}); setError("بازهٔ تحویل دیگر ظرفیت ندارد؛ زمان تازه را انتخاب کنید."); } } })
      .catch(() => { if (!controller.signal.aborted) setQuote(null); });
    return () => controller.abort();
  }, [selectedAddressId, cart, shippingMethods, shippingSlots]);
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
  return <div className="catalog-shell"><header className="site-header"><div className="header-inner"><a className="brand" href="/">گزیناو</a><a href="/products/">محصولات</a></div></header><main className="catalog-main"><h1>سبد خرید</h1>
    {error && <p role="alert">{error}</p>}{signedOut ? <p>برای دیدن سبد خرید <a href="/login/">وارد شوید</a>.</p> : !cart ? <p>در حال بارگذاری...</p> : cart.lines.length === 0 ? <p>سبد خرید خالی است. <a href="/products/">محصولات را ببینید</a>.</p> : <><ul className="admin-list">{cart.lines.map((line) => <li className="cart-line" key={line.id}><div><a href={`/products/${encodeURIComponent(line.product_slug)}/`}><strong>{line.product_title}</strong></a><p>{Object.entries(line.variant).map(([key, value]) => `${key}: ${value}`).join(" · ")} · {line.seller}</p><p>قیمت واحد: {line.unit_price_toman.toLocaleString("fa-IR")} تومان</p>{!line.available && <p className="cart-warning">موجودی یا وضعیت این پیشنهاد تغییر کرده است.</p>}</div><div><b>{line.line_total_toman.toLocaleString("fa-IR")} تومان</b><div className="cart-actions"><label>تعداد<select value={line.quantity} onChange={(event) => void change(line.id, Number(event.target.value))}>{Array.from({ length: Math.min(100, Math.max(line.quantity, line.free_stock)) }, (_, index) => index + 1).map((number) => <option key={number} value={number}>{number}</option>)}</select></label><button type="button" onClick={() => void remove(line.id)}>حذف</button></div></div></li>)}</ul><section className="admin-card"><h2>نشانی تحویل</h2><label>نشانی ذخیره‌شده<select value={selectedAddressId} onChange={(event) => setSelectedAddressId(event.target.value)}><option value="">انتخاب نشانی</option>{addresses.map((address) => <option key={address.id} value={address.id}>{address.province}، {address.city}، {address.street}</option>)}</select></label><form className="admin-inline-form" onSubmit={addAddress}><label>نام گیرنده<input required value={fullName} onChange={(event) => setFullName(event.target.value)} /></label><label>شمارهٔ همراه<input required inputMode="tel" value={phone} onChange={(event) => setPhone(event.target.value)} /></label><label>استان<input required value={province} onChange={(event) => setProvince(event.target.value)} /></label><label>شهر<input required value={city} onChange={(event) => setCity(event.target.value)} /></label><label>نشانی<input required value={street} onChange={(event) => setStreet(event.target.value)} /></label><label>کد پستی<input required inputMode="numeric" value={postalCode} onChange={(event) => setPostalCode(event.target.value)} /></label><button type="submit">افزودن نشانی</button></form></section><section className="admin-card seller-section"><h2>برآورد سبد خرید</h2><CartCoupon code={cart.coupon_code} reload={load} /><p>جمع کالاها: <strong>{(quote?.item_subtotal_toman ?? cart.estimated_subtotal_toman).toLocaleString("fa-IR")} تومان</strong></p>{quote?.ready ? <><h3>جزئیات مبلغ برای تأیید</h3><ul>{quote.lines.map((line) => <li key={line.id}>{line.product_title} · {line.seller} · {line.quantity} عدد × {line.unit_price_toman.toLocaleString("fa-IR")} تومان · ضمانت: {line.warranty || "ثبت نشده"} · مالیات: {line.tax.amount_toman.toLocaleString("fa-IR")} تومان ({(line.tax.rate_bps / 100).toLocaleString("fa-IR")}%{line.tax.label && ` · ${line.tax.label}`})</li>)}</ul><p>تخفیف: {quote.discount_total_toman.toLocaleString("fa-IR")} تومان</p><p>مالیات کالاها پس از تخفیف: {quote.tax_total_toman.toLocaleString("fa-IR")} تومان</p><p>هزینهٔ ارسال: {quote.shipping_total_toman?.toLocaleString("fa-IR")} تومان</p><p><strong>برآورد کل: {quote.estimated_total_toman?.toLocaleString("fa-IR")} تومان</strong></p><ul>{quote.deliveries.map((delivery, index) => <li key={index}>{delivery.seller}: <label>روش ارسال<select value={delivery.id} onChange={(event) => { setQuote(null); setShippingSlots((previous) => ({ ...previous, [delivery.group_key]: 0 })); setShippingMethods((previous) => ({ ...previous, [delivery.group_key]: Number(event.target.value) })); }}>{delivery.options.map((option) => <option key={option.id} value={option.id}>{option.label} · {option.fee_toman.toLocaleString("fa-IR")} تومان · {option.min_days} تا {option.max_days} روز</option>)}</select></label>{delivery.windows.length > 0 && <label>بازهٔ تحویل<select value={delivery.window?.id ?? 0} onChange={(event) => { setQuote(null); setShippingSlots((previous) => ({ ...previous, [delivery.group_key]: Number(event.target.value) })); }}><option value={0}>بدون بازهٔ مشخص</option>{delivery.windows.map((window) => <option key={window.id} value={window.id}>{new Date(window.starts_at).toLocaleString("fa-IR")} تا {new Date(window.ends_at).toLocaleString("fa-IR")}</option>)}</select></label>} {delivery.window ? `${new Date(delivery.window.starts_at).toLocaleString("fa-IR")} تا ${new Date(delivery.window.ends_at).toLocaleString("fa-IR")}` : `${delivery.min_days} تا ${delivery.max_days} روز`} · {delivery.fee_toman.toLocaleString("fa-IR")} تومان</li>)}</ul></> : <p>برای برآورد ارسال، نشانی معتبر و قوانین ارسال لازم است.</p>}<p>این برآورد ده دقیقه اعتبار دارد و موجودی را رزرو نمی‌کند. تغییر مبلغ، نشانی یا زمان ارسال به تأیید دوباره نیاز دارد.</p>{!cart.can_checkout && <p className="cart-warning">برای ادامه، کالاهای ناموجود را اصلاح یا حذف کنید.</p>}{quote?.coupon_error && <p role="alert">کوپن دیگر معتبر نیست؛ آن را حذف یا جایگزین کنید.</p>}<button type="button" onClick={() => { setQuote(null); void load(); }}>تازه‌سازی برآورد</button><CheckoutAction addressId={Number(selectedAddressId)} ready={Boolean(quote?.ready && cart.can_checkout)} quoteToken={quote?.approval_token ?? null} shippingMethods={shippingMethods} shippingSlots={shippingSlots} refreshQuote={async () => { setQuote(null); await load(); }} /></section></>}
  </main></div>;
}
