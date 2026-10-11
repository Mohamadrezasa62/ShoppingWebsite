"use client";
import { FormEvent, useState } from "react";
type Report = { seller: { id: number; name: string; status: string }; warehouses: { id: number; name: string; active: boolean; default: boolean }[]; offers: { id: number; product: string; sku: string; managed: boolean; quantity: number; reserved: number; balances: { id: number; warehouse: string; quantity: number; reserved: number; free: number }[] }[]; next_after_id: number | null };
export function AdminInventory() {
  const [sellerId, setSellerId] = useState(""); const [report, setReport] = useState<Report | null>(null); const [notice, setNotice] = useState(""); const [busy, setBusy] = useState(false);
  async function load(after = 0, id = sellerId) {
    setBusy(true);
    try { const response = await fetch(`/api/v1/operations/inventory/?seller_id=${encodeURIComponent(id)}&after_id=${after}`); if (!response.ok) throw new Error(); setReport(await response.json()); setNotice(""); }
    catch { setNotice("گزارش دریافت نشد؛ شمارهٔ فروشنده و دسترسی را بررسی کنید."); } finally { setBusy(false); }
  }
  function submit(event: FormEvent<HTMLFormElement>) { event.preventDefault(); void load(); }
  return <section className="admin-card"><h1>نمای موجودی فروشنده</h1><form className="admin-inline-form" onSubmit={submit}><label>شمارهٔ فروشنده<input value={sellerId} onChange={(event) => setSellerId(event.target.value)} type="number" min={1} required /></label><button disabled={busy}>دریافت گزارش</button></form>{notice && <p role="status">{notice}</p>}{report && <><h2>{report.seller.name} · #{report.seller.id}</h2><p>این گزارش برای مشاهدهٔ موجودی و رزروهاست؛ اصلاح موجودی از پنل فروشنده با ثبت دلیل انجام می‌شود.</p><ul>{report.warehouses.map((row) => <li key={row.id}>{row.name} · {row.active ? "فعال" : "غیرفعال"}{row.default && " · اصلی"}</li>)}</ul><ul className="admin-list">{report.offers.map((offer) => <li key={offer.id}><h3>{offer.product} · <span dir="ltr">{offer.sku}</span></h3><p>پیشنهاد #{offer.id} · کل {offer.quantity} · رزرو {offer.reserved}</p>{!offer.managed && <p>هنوز به مدیریت انبار منتقل نشده است.</p>}<ul>{offer.balances.map((row) => <li key={row.id}>{row.warehouse} · کل {row.quantity} · رزرو {row.reserved} · آزاد {row.free}</li>)}</ul></li>)}</ul><button disabled={busy} onClick={() => void load(0, String(report.seller.id))}>صفحهٔ اول</button><button disabled={busy || report.next_after_id === null} onClick={() => report.next_after_id !== null && void load(report.next_after_id, String(report.seller.id))}>صفحهٔ بعد</button></>}</section>;
}
