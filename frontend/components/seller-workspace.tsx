"use client";

import { FormEvent, useCallback, useEffect, useState } from "react";
import { InventoryWorkspace } from "@/components/inventory-workspace";
import { DisputeWorkspace } from "@/components/dispute-workspace";
import { apiRequest } from "@/lib/api";
import { SellerTools } from "@/components/seller-tools";
import { SellerFulfillment } from "@/components/fulfillment-workspace";

type Store = { id: number; name: string; status: string; role: string; description: string; contact_phone: string };
type Variant = { id: number; sku: string; product_title: string; attributes: Record<string, string> };
type Offer = { id: number; variant_id: number; product_title: string; sku: string; price_toman: number; available_quantity: number; reserved_quantity: number; warranty: string; fulfillment: string; status: string; inventory_managed: boolean };

const statusLabels: Record<string, string> = { applied: "در انتظار بررسی", under_review: "در حال بررسی", approved: "تأییدشده", rejected: "ردشده", suspended: "معلق" };

function OfferRow({ offer, storeId, changed }: { offer: Offer; storeId: number; changed: () => void }) {
  const [price, setPrice] = useState(String(offer.price_toman));
  const [stock, setStock] = useState(String(offer.available_quantity));
  const [warranty, setWarranty] = useState(offer.warranty);
  const [status, setStatus] = useState(offer.status === "active" ? "active" : "paused");
  const [message, setMessage] = useState("");
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const response = await apiRequest("PATCH", `/api/v1/seller/stores/${storeId}/offers/${offer.id}/`, { price_toman: Number(price), ...(offer.inventory_managed ? {} : { available_quantity: Number(stock) }), warranty, status });
    if (response.ok) { setMessage("ذخیره شد."); changed(); }
    else { const result = await response.json(); setMessage(result.error === "stock_below_reserved" ? "موجودی کمتر از تعداد رزروشده است." : "ذخیره انجام نشد."); }
  }
  return <li className="admin-record"><strong>{offer.product_title}</strong><p dir="ltr">SKU: {offer.sku}</p><p>موجودی رزروشده: {offer.reserved_quantity.toLocaleString("fa-IR")}</p>
    <form className="admin-inline-form" onSubmit={submit}>
      <label>قیمت (تومان)<input type="number" min="1" required value={price} onChange={(event) => setPrice(event.target.value)} /></label>
      <label>موجودی کل<input disabled={offer.inventory_managed} type="number" min={offer.reserved_quantity} required value={stock} onChange={(event) => setStock(event.target.value)} /></label>
      <label>گارانتی<input maxLength={200} value={warranty} onChange={(event) => setWarranty(event.target.value)} /></label>
      <label>وضعیت<select value={status} onChange={(event) => setStatus(event.target.value)}><option value="active">فعال</option><option value="paused">متوقف</option></select></label>
      <button type="submit">ذخیرهٔ پیشنهاد</button>{message && <span role="status">{message}</span>}
    </form>{offer.inventory_managed && <p>موجودی را در بخش انبارها و موجودی اصلاح کنید.</p>}</li>;
}

export function SellerWorkspace() {
  const [stores, setStores] = useState<Store[]>([]);
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [offers, setOffers] = useState<Offer[]>([]);
  const [variants, setVariants] = useState<Variant[]>([]);
  const [applicationName, setApplicationName] = useState("");
  const [legalName, setLegalName] = useState("");
  const [businessIdentifier, setBusinessIdentifier] = useState("");
  const [applicationPhone, setApplicationPhone] = useState("");
  const [description, setDescription] = useState("");
  const [profilePhone, setProfilePhone] = useState("");
  const [query, setQuery] = useState("");
  const [variantId, setVariantId] = useState("");
  const [price, setPrice] = useState("");
  const [stock, setStock] = useState("");
  const [warranty, setWarranty] = useState("");
  const [notice, setNotice] = useState("");
  const [error, setError] = useState("");
  const [signedOut, setSignedOut] = useState(false);

  const loadStores = useCallback(async () => {
    try {
      const response = await fetch("/api/v1/seller/stores/", { credentials: "same-origin" });
      if (response.status === 401) { setSignedOut(true); return; }
      if (!response.ok) throw new Error();
      const data = await response.json();
      setStores(data.stores);
      setSelectedId((current) => current && data.stores.some((store: Store) => store.id === current) ? current : data.stores[0]?.id ?? null);
    } catch { setError("فروشگاه‌ها بارگذاری نشدند."); }
  }, []);
  const loadOffers = useCallback(async (storeId: number) => {
    try {
      const response = await fetch(`/api/v1/seller/stores/${storeId}/offers/`, { credentials: "same-origin" });
      if (!response.ok) throw new Error();
      setOffers((await response.json()).offers);
    } catch { setError("پیشنهادها بارگذاری نشدند."); }
  }, []);
  useEffect(() => { void loadStores(); }, [loadStores]);
  const selected = stores.find((store) => store.id === selectedId);
  useEffect(() => { setDescription(selected?.description ?? ""); setProfilePhone(selected?.contact_phone ?? ""); }, [selected?.id, selected?.description, selected?.contact_phone]);
  useEffect(() => { if (selected?.status === "approved") void loadOffers(selected.id); else setOffers([]); }, [selected?.id, selected?.status, loadOffers]);

  async function apply(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); setError("");
    const response = await apiRequest("POST", "/api/v1/seller/applications/", { name: applicationName, legal_name: legalName, business_identifier: businessIdentifier, contact_phone: applicationPhone });
    if (response.ok) { setApplicationName(""); setLegalName(""); setBusinessIdentifier(""); setApplicationPhone(""); setNotice("درخواست فروشگاه ثبت شد."); await loadStores(); }
    else setError("ثبت درخواست انجام نشد.");
  }
  async function search(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); setError("");
    if (query.trim().length < 2) { setVariants([]); return; }
    try {
      const response = await fetch(`/api/v1/seller/catalog-variants/?q=${encodeURIComponent(query)}`, { credentials: "same-origin" });
      if (!response.ok) throw new Error();
      setVariants((await response.json()).variants);
    } catch { setError("جست‌وجوی مدل انجام نشد."); }
  }
  async function createOffer(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); if (!selectedId) return;
    const response = await apiRequest("POST", `/api/v1/seller/stores/${selectedId}/offers/`, { variant_id: Number(variantId), price_toman: Number(price), available_quantity: Number(stock), warranty });
    if (response.ok) { setNotice("پیشنهاد ثبت شد."); setVariantId(""); setPrice(""); setStock(""); setWarranty(""); void loadOffers(selectedId); }
    else { const result = await response.json(); setError(result.error === "offer_already_exists" ? "برای این مدل از این فروشگاه پیشنهادی وجود دارد." : "ثبت پیشنهاد انجام نشد."); }
  }
  async function saveProfile(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); if (!selectedId) return;
    const response = await apiRequest("PATCH", `/api/v1/seller/stores/${selectedId}/profile/`, { description, contact_phone: profilePhone });
    if (response.ok) { setNotice("اطلاعات فروشگاه ذخیره شد."); await loadStores(); }
    else setError("اطلاعات فروشگاه ذخیره نشد.");
  }

  return <div className="admin-shell"><header className="admin-header"><a href="/" className="brand">گزیناو</a><span>پنل فروشنده</span><a href="/account/">حساب من</a></header><main className="catalog-main">
    <h1>فروشگاه‌های من</h1>{error && <p className="admin-alert" role="alert">{error}</p>}{notice && <p className="admin-alert" role="status">{notice}</p>}
    {signedOut ? <p>برای ثبت فروشگاه و مدیریت پیشنهادها <a href="/login/">وارد شوید</a>.</p> : <>
      <div className="seller-store-list">{stores.map((store) => <button type="button" key={store.id} className={selectedId === store.id ? "selected" : ""} onClick={() => setSelectedId(store.id)}>{store.name} · {statusLabels[store.status] ?? store.status}</button>)}</div>
      {selected && <DisputeWorkspace key={`disputes-${selected.id}`} sellerId={selected.id} />}
      {selected?.status === "approved" && <InventoryWorkspace key={`inventory-${selected.id}`} storeId={selected.id} owner={selected.role === "owner"} changed={() => void loadOffers(selected.id)} />}
      {selected && <SellerTools key={`tools-${selected.id}`} storeId={selected.id} />}
      {selected && <SellerFulfillment key={selected.id} storeId={selected.id} />}
      <section className="admin-card"><h2>درخواست فروشگاه</h2><form className="admin-inline-form" onSubmit={apply}><label>نام فروشگاه<input minLength={3} maxLength={200} required value={applicationName} onChange={(event) => setApplicationName(event.target.value)} /></label><label>نام قانونی<input minLength={3} maxLength={200} required value={legalName} onChange={(event) => setLegalName(event.target.value)} /></label><label>شناسهٔ کسب‌وکار<input minLength={8} maxLength={32} required value={businessIdentifier} onChange={(event) => setBusinessIdentifier(event.target.value)} /></label><label>شمارهٔ تماس<input inputMode="tel" required value={applicationPhone} onChange={(event) => setApplicationPhone(event.target.value)} /></label><button type="submit">ثبت درخواست</button></form><p>پس از بررسی و تأیید مدیر بازارگاه، مدیریت پیشنهادها فعال می‌شود.</p></section>
      {selected && selected.status !== "approved" && <section className="admin-card seller-section"><h2>{selected.name}</h2><p>وضعیت درخواست: {statusLabels[selected.status] ?? selected.status}</p></section>}
      {selected?.status === "approved" && <><section className="admin-card seller-section"><h2>پروفایل {selected.name}</h2><form className="admin-inline-form" onSubmit={saveProfile}><label>توضیح فروشگاه<input maxLength={2000} value={description} onChange={(event) => setDescription(event.target.value)} /></label><label>شمارهٔ تماس<input inputMode="tel" value={profilePhone} onChange={(event) => setProfilePhone(event.target.value)} /></label><button type="submit">ذخیرهٔ پروفایل</button></form></section><section className="admin-card seller-section"><h2>افزودن پیشنهاد به {selected.name}</h2><form className="admin-inline-form" onSubmit={search}><label>جست‌وجوی محصول یا کد مدل<input value={query} onChange={(event) => setQuery(event.target.value)} /></label><button type="submit">جست‌وجو</button></form>
        <form className="admin-inline-form" onSubmit={createOffer}><label>مدل<select required value={variantId} onChange={(event) => setVariantId(event.target.value)}><option value="">انتخاب مدل</option>{variants.map((variant) => <option key={variant.id} value={variant.id}>{variant.product_title} · {variant.sku} · {Object.values(variant.attributes).join(" / ")}</option>)}</select></label>
          <label>قیمت (تومان)<input type="number" min="1" required value={price} onChange={(event) => setPrice(event.target.value)} /></label><label>موجودی<input type="number" min="0" required value={stock} onChange={(event) => setStock(event.target.value)} /></label><label>گارانتی<input maxLength={200} value={warranty} onChange={(event) => setWarranty(event.target.value)} /></label><button type="submit">ثبت پیشنهاد</button></form>
      </section><section className="admin-card seller-section"><h2>پیشنهادهای {selected.name}</h2><ul className="admin-list">{offers.map((offer) => <OfferRow key={offer.id} offer={offer} storeId={selected.id} changed={() => void loadOffers(selected.id)} />)}</ul>{offers.length === 0 && <p>هنوز پیشنهادی ثبت نشده است.</p>}</section></>}
    </>}
  </main></div>;
}
