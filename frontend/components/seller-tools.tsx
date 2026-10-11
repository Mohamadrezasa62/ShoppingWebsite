"use client";
import { FormEvent, useEffect, useState } from "react";
import { ProductProposals } from "@/components/product-proposals";
import { csrfToken } from "@/lib/api";
type Performance = { paid_item_tax_toman: number; refunded_tax_toman: number; paid_orders: number; paid_item_total_toman: number; delivered_units: number; refunded_units: number; low_stock_offers: number };
type Finance = { recognized_payable_toman: number; commission_toman: number; unsettled_payable_toman: number; settlements: { id: number; amount_toman: number; status: string }[] };
export function SellerTools({ storeId }: { storeId: number }) {
  const [performance, setPerformance] = useState<Performance | null>(null);
  const [finance, setFinance] = useState<Finance | null>(null); const [notice, setNotice] = useState(""); const [busy, setBusy] = useState(false);
  useEffect(() => { let active = true; setFinance(null); fetch(`/api/v1/seller/stores/${storeId}/finance/`).then(async (response) => { if (!response.ok) throw new Error(); const data = await response.json(); if (active) setFinance(data); }).catch(() => { if (active) setNotice("گزارش مالی دریافت نشد."); }); return () => { active = false; }; }, [storeId]);
  useEffect(() => { let active = true; setPerformance(null); fetch(`/api/v1/seller/stores/${storeId}/performance/`).then(async response => { if (!response.ok) throw new Error(); const data = await response.json(); if (active) setPerformance(data); }).catch(() => { if (active) setNotice("گزارش عملکرد دریافت نشد."); }); return () => { active = false; }; }, [storeId]);
  async function upload(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); setBusy(true); const form = event.currentTarget;
    try {
      const csrf = await fetch("/api/v1/auth/csrf/", { credentials: "same-origin" }); if (!csrf.ok) throw new Error();
      const response = await fetch(`/api/v1/seller/stores/${storeId}/offers-csv/`, { method: "POST", credentials: "same-origin", headers: { "X-CSRFToken": csrfToken() ?? "" }, body: new FormData(form) });
      const result = await response.json(); if (!response.ok) throw new Error(`فایل رد شد: ${result.details ?? result.error}`);
      setNotice(`${result.updated} پیشنهاد به‌روزرسانی شد؛ فهرست پیشنهادها را بازخوانی کنید.`); form.reset();
    } catch (error) { setNotice(error instanceof Error ? error.message : "بارگذاری انجام نشد."); } finally { setBusy(false); }
  }
  return <><ProductProposals storeId={storeId} /><section className="admin-card seller-section"><h2>ابزارها و گزارش مالی</h2>{notice && <p role="status">{notice}</p>}<a href={`/api/v1/seller/stores/${storeId}/offers-csv/`}>دریافت فایل CSV پیشنهادها</a><p>فایل دریافت‌شده را با همان ستون‌ها ویرایش کنید؛ فایل نامعتبر به صورت کامل رد می‌شود. برای پیشنهاد چندانباره، موجودی کل را در این فایل تغییر ندهید؛ از بخش موجودی انبار استفاده کنید.</p><form className="admin-inline-form" onSubmit={upload}><label>فایل CSV<input name="file" type="file" accept=".csv,text/csv" required /></label><button disabled={busy}>به‌روزرسانی گروهی</button></form>{performance && <><h3>عملکرد از آغاز فعالیت</h3><p>سفارش‌های پرداخت‌شده: {performance.paid_orders} · واحد تحویل‌شده: {performance.delivered_units} · واحد مستردشده: {performance.refunded_units}</p><p>جمع اقلام پس از تخفیف، بدون ارسال و مالیات: {performance.paid_item_total_toman.toLocaleString("fa-IR")} تومان · پیشنهادهای با موجودی کم: {performance.low_stock_offers}</p><p>مالیات اقلام پرداخت‌شده: {performance.paid_item_tax_toman.toLocaleString("fa-IR")} تومان · مالیات مستردشده: {performance.refunded_tax_toman.toLocaleString("fa-IR")} تومان</p></>}{finance && <><p>مطالبات ثبت‌شده: {finance.recognized_payable_toman.toLocaleString("fa-IR")} تومان</p><p>کمیسیون ثبت‌شده: {finance.commission_toman.toLocaleString("fa-IR")} تومان</p><p>ثبت‌های تخصیص‌نیافته به تسویه: {finance.unsettled_payable_toman.toLocaleString("fa-IR")} تومان</p><p>مبالغ پس از ثبت مطالبات تحویل‌شده توسط مالی نمایش داده می‌شوند؛ این گزارش موجودی قابل برداشت بانکی نیست.</p><ul>{finance.settlements.map((row) => <li key={row.id}>تسویه #{row.id} · {row.status} · {row.amount_toman.toLocaleString("fa-IR")} تومان</li>)}</ul></>}</section></>;
}
