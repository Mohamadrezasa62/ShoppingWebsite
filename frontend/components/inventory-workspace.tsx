"use client";
import { FormEvent, useCallback, useEffect, useRef, useState } from "react";
import { apiRequest, csrfToken } from "@/lib/api";
type Warehouse = { id: number; name: string; code: string; active: boolean; default: boolean };
type Balance = { id: number; warehouse_id: number; warehouse: string; quantity: number; reserved: number; free: number; version: number };
type Offer = { id: number; sku: string; product: string; managed: boolean; quantity: number; reserved: number; balances: Balance[] };
type Movement = { id: number; warehouse: string; kind: string; quantity_delta: number; reserved_delta: number; reason: string; created_at: string };
const errorLabels: Record<string, string> = { stock_version_conflict: "موجودی تغییر کرده است؛ تازه‌سازی کنید و دوباره تصمیم بگیرید.", insufficient_free_stock: "موجودی آزاد برای انتقال کافی نیست.", stock_below_reserved_or_capacity: "موجودی نباید کمتر از رزروها یا بیشتر از سقف مجاز باشد.", inventory_inconsistent: "موجودی نیاز به بررسی عملیات دارد.", legacy_inventory_inconsistent: "رزروهای قبلی نیاز به بررسی عملیات دارند.", warehouse_has_stock_or_default: "انبار اصلی یا انباری که موجودی دارد غیرفعال نمی‌شود.", warehouse_code_conflict: "این کد انبار قبلاً استفاده شده است.", warehouse_unavailable: "انبار فعال نیست.", stock_transfer_conflict: "درخواست انتقال با ثبت قبلی یکسان نیست.", seller_approval_required: "دسترسی یا تأیید فروشگاه را بررسی کنید.", warehouse_limit: "سقف تعداد انبارها پر شده است." };

function StockOffer({ offer, warehouses, base, changed }: { offer: Offer; warehouses: Warehouse[]; base: string; changed: () => Promise<void> }) {
  const [busy, setBusy] = useState(false); const [notice, setNotice] = useState(""); const [history, setHistory] = useState<Movement[] | null>(null); const transferKey = useRef("");
  async function execute(action: string, data: unknown) {
    setBusy(true);
    try { const response = await apiRequest("POST", `${base}inventory/${offer.id}/${action}/`, data); if (!response.ok) { const result = await response.json(); throw new Error(errorLabels[result.error] ?? "عملیات انجام نشد؛ اطلاعات را بررسی کنید."); } setNotice("ثبت شد."); await changed(); return true; }
    catch (error) { setNotice(error instanceof Error ? error.message : "ارتباط برقرار نشد."); return false; } finally { setBusy(false); }
  }
  async function adjust(event: FormEvent<HTMLFormElement>, balance?: Balance) {
    event.preventDefault(); const data = new FormData(event.currentTarget);
    await execute("adjust", { warehouse_id: balance?.warehouse_id ?? Number(data.get("warehouse")), quantity: Number(data.get("quantity")), version: balance?.version ?? 0, reason: data.get("reason") });
  }
  async function transfer(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); const form = event.currentTarget; const data = new FormData(form); if (!transferKey.current) transferKey.current = crypto.randomUUID();
    if (await execute("transfer", { source_id: Number(data.get("source")), destination_id: Number(data.get("destination")), quantity: Number(data.get("quantity")), request_key: transferKey.current, reason: data.get("reason") })) { transferKey.current = ""; form.reset(); }
  }
  async function loadHistory() {
    try { const response = await fetch(`${base}inventory/${offer.id}/history/`); if (!response.ok) throw new Error(); setHistory((await response.json()).movements); }
    catch { setNotice("تاریخچه دریافت نشد."); }
  }
  const active = warehouses.filter((row) => row.active);
  const newWarehouses = active.filter((row) => !offer.balances.some((balance) => balance.warehouse_id === row.id));
  return <li className="admin-record"><h3>{offer.product} · <span dir="ltr">{offer.sku}</span></h3><p>موجودی کل: {offer.quantity.toLocaleString("fa-IR")} · رزروشده: {offer.reserved.toLocaleString("fa-IR")}</p>{notice && <p role="status">{notice}</p>}{!offer.managed ? <form className="admin-inline-form" onSubmit={(event) => { event.preventDefault(); void execute("activate", { reason: new FormData(event.currentTarget).get("reason") }); }}><p>موجودی فعلی و رزروهای باز به انبار اصلی منتقل شوند.</p><label>دلیل<input name="reason" required minLength={3} maxLength={500} /></label><button disabled={busy}>فعال‌کردن مدیریت انبار</button></form> : <><ul className="admin-list">{offer.balances.map((balance) => <li key={balance.id}><strong>{balance.warehouse}</strong><p>کل: {balance.quantity} · رزرو: {balance.reserved} · آزاد: {balance.free}</p><form key={`${balance.id}-${balance.version}`} className="admin-inline-form" onSubmit={(event) => void adjust(event, balance)}><label>موجودی فیزیکی جدید<input name="quantity" type="number" defaultValue={balance.quantity} min={balance.reserved} max={2147483647} required /></label><label>دلیل اصلاح<input name="reason" required minLength={3} maxLength={500} /></label><button disabled={busy}>ثبت موجودی این انبار</button></form></li>)}</ul>{newWarehouses.length > 0 && <details><summary>ثبت موجودی در انبار دیگر</summary><form className="admin-inline-form" onSubmit={(event) => void adjust(event)}><label>انبار<select name="warehouse">{newWarehouses.map((row) => <option key={row.id} value={row.id}>{row.name}</option>)}</select></label><label>تعداد<input name="quantity" type="number" min={0} max={2147483647} required /></label><label>دلیل<input name="reason" required minLength={3} maxLength={500} /></label><button disabled={busy}>ثبت موجودی</button></form></details>}{active.length > 1 && <details><summary>انتقال موجودی آزاد بین انبارها</summary><form className="admin-inline-form" onSubmit={transfer} onChange={() => { transferKey.current = ""; }}><label>مبدأ<select name="source" disabled={busy}>{active.map((row) => <option key={row.id} value={row.id}>{row.name}</option>)}</select></label><label>مقصد<select name="destination" disabled={busy}>{active.map((row) => <option key={row.id} value={row.id}>{row.name}</option>)}</select></label><label>تعداد<input name="quantity" type="number" min={1} max={2147483647} required disabled={busy} /></label><label>دلیل<input name="reason" required minLength={3} maxLength={500} disabled={busy} /></label><button disabled={busy}>انتقال</button></form></details>}<button onClick={() => void loadHistory()}>۱۰۰ رویداد آخر موجودی</button>{history && <ul>{history.map((row) => <li key={row.id}>{row.warehouse} · {row.kind} · تغییر موجودی {row.quantity_delta} · تغییر رزرو {row.reserved_delta}<p>{row.reason} · {new Date(row.created_at).toLocaleString("fa-IR")}</p></li>)}</ul>}</>}</li>;
}

export function InventoryWorkspace({ storeId, owner, changed }: { storeId: number; owner: boolean; changed: () => void }) {
  const [warehouses, setWarehouses] = useState<Warehouse[]>([]); const [offers, setOffers] = useState<Offer[]>([]); const [after, setAfter] = useState(0); const [next, setNext] = useState<number | null>(null); const [notice, setNotice] = useState(""); const [busy, setBusy] = useState(false);
  const base = `/api/v1/seller/stores/${storeId}/`;
  const load = useCallback(async () => {
    try {
      const [stock, locations] = await Promise.all([fetch(`${base}inventory/?after_id=${after}`), fetch(`${base}warehouses/`)]);
      if (!stock.ok || !locations.ok) throw new Error(); const data = await stock.json(); setOffers(data.offers); setNext(data.next_after_id); setWarehouses((await locations.json()).warehouses);
    } catch { setNotice("موجودی دریافت نشد؛ دسترسی فروشگاه را بررسی کنید."); }
  }, [base, after]);
  useEffect(() => { void load(); }, [load]);
  async function refresh() { await load(); changed(); }
  async function createWarehouse(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); const form = event.currentTarget; const data = new FormData(form); setBusy(true);
    try { const response = await apiRequest("POST", `${base}warehouses/`, { name: data.get("name"), code: data.get("code"), reason: data.get("reason") }); if (!response.ok) { const result = await response.json(); throw new Error(errorLabels[result.error] ?? "انبار ثبت نشد."); } form.reset(); await load(); }
    catch (error) { setNotice(error instanceof Error ? error.message : "ارتباط برقرار نشد."); } finally { setBusy(false); }
  }
  async function editWarehouse(event: FormEvent<HTMLFormElement>, id: number) {
    event.preventDefault(); const data = new FormData(event.currentTarget); setBusy(true);
    try { const response = await apiRequest("PATCH", `${base}warehouses/${id}/`, { name: data.get("name"), active: data.get("active") === "on", reason: data.get("reason") }); if (!response.ok) { const result = await response.json(); throw new Error(errorLabels[result.error] ?? "انبار تغییر نکرد."); } await load(); }
    catch (error) { setNotice(error instanceof Error ? error.message : "ارتباط برقرار نشد."); } finally { setBusy(false); }
  }
  const importKey = useRef(""); const [exportAfter, setExportAfter] = useState("0"); const [exportDone, setExportDone] = useState(false);
  async function uploadCsv(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); const form = event.currentTarget; const data = new FormData(form); setBusy(true); if (!importKey.current) importKey.current = crypto.randomUUID(); data.set("request_key", importKey.current);
    try { await fetch("/api/v1/auth/csrf/", { credentials: "same-origin" }); const response = await fetch(`${base}inventory-csv/`, { method: "POST", credentials: "same-origin", headers: { "X-CSRFToken": csrfToken() ?? "" }, body: data }); const result = await response.json(); if (!response.ok) throw new Error(errorLabels[result.error] ?? "فایل رد شد؛ ستون‌ها، نسخهٔ موجودی و انبار را بررسی کنید."); form.reset(); importKey.current = ""; await refresh(); setNotice(`${result.updated} ردیف موجودی ثبت شد.`); }
    catch (error) { setNotice(error instanceof Error ? error.message : "بارگذاری انجام نشد."); } finally { setBusy(false); }
  }
  async function downloadCsv() {
    setBusy(true);
    try { const response = await fetch(`${base}inventory-csv/?after_id=${exportAfter}`); if (!response.ok) throw new Error(); const url = URL.createObjectURL(await response.blob()); const anchor = document.createElement("a"); anchor.href = url; anchor.download = `warehouse-stock-${exportAfter}.csv`; anchor.click(); setTimeout(() => URL.revokeObjectURL(url), 1000); const cursor = response.headers.get("X-Next-Balance-ID") ?? "0"; setExportAfter(cursor); setExportDone(cursor === "0"); }
    catch { setNotice("خروجی دریافت نشد."); } finally { setBusy(false); }
  }
  return <section className="admin-card seller-section"><h2>انبارها و موجودی</h2><p>رزرو سفارش از موجودی آزاد انبارها انجام می‌شود. انتقال فقط موجودی آزاد را جابه‌جا می‌کند و مرجوعی تأییدشده به انبار اولیه برمی‌گردد.</p><button onClick={() => void refresh()}>تازه‌سازی موجودی</button><details><summary>ورود و خروج گروهی موجودی انبار</summary><p>فایل UTF-8 با ستون‌های sku، warehouse_code، quantity و version؛ حداکثر ۵۰۰ ردیف و ۲۵۶ کیلوبایت. از نسخهٔ موجودی تازه استفاده کنید؛ خطای یک ردیف، کل فایل را برمی‌گرداند. برای موجودی جدید در انبار، version را صفر بگذارید. سلول‌های شبیه فرمول در خروجی با آپاستروف امن می‌شوند؛ شناسه‌های اصلی را پیش از ورود بررسی کنید.</p><button disabled={busy || exportDone} onClick={() => void downloadCsv()}>دریافت بخش بعدی CSV (۵۰۰ ردیف)</button><button disabled={busy} onClick={() => { setExportAfter("0"); setExportDone(false); }}>شروع خروجی از ابتدا</button>{exportDone && <p>خروجی تمام شد.</p>}<form className="admin-inline-form" onSubmit={uploadCsv} onChange={() => { importKey.current = ""; }}><label>فایل CSV<input type="file" name="file" accept=".csv,text/csv" required disabled={busy} /></label><label>دلیل<input name="reason" required minLength={3} maxLength={500} disabled={busy} /></label><button disabled={busy}>ثبت گروهی موجودی</button></form></details>{notice && <p role="status">{notice}</p>}{owner && <details><summary>مدیریت انبارها</summary><form className="admin-inline-form" onSubmit={createWarehouse}><label>نام<input name="name" required minLength={3} maxLength={160} /></label><label>کد لاتین<input name="code" required pattern="[A-Za-z0-9_-]+" maxLength={80} /></label><label>دلیل<input name="reason" required minLength={3} maxLength={500} /></label><button disabled={busy}>انبار جدید</button></form>{warehouses.map((row) => <form key={`${row.id}-${row.name}-${row.active}`} className="admin-inline-form" onSubmit={(event) => void editWarehouse(event, row.id)}><label>نام<input name="name" defaultValue={row.name} required minLength={3} maxLength={160} /></label><span>{row.code}{row.default && " · انبار اصلی"}</span><label><input name="active" type="checkbox" defaultChecked={row.active} /> فعال</label><label>دلیل<input name="reason" required minLength={3} maxLength={500} /></label><button disabled={busy}>ذخیره</button></form>)}</details>}<ul className="admin-list">{offers.map((offer) => <StockOffer key={offer.id} offer={offer} warehouses={warehouses} base={base} changed={refresh} />)}</ul>{!offers.length && <p>پیشنهادی در این صفحه نیست.</p>}<button disabled={after === 0} onClick={() => setAfter(0)}>صفحهٔ اول</button><button disabled={next === null} onClick={() => next !== null && setAfter(next)}>صفحهٔ بعد</button></section>;
}
