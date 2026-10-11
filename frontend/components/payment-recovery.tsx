"use client";
import { FormEvent, useCallback, useEffect, useRef, useState } from "react";
import { apiRequest } from "@/lib/api";
import { PaymentInvestigation } from "@/components/payment-investigation";
import { paymentDestination } from "@/lib/payment-redirect";

type Payment = { id: number; order_id: number; provider: string; status: string; amount_toman: number; captured_toman: number; refunded_toman: number; receipt: string; can_verify: boolean; checkout_url: string; needs_provider_reconciliation: boolean };
const labels: Record<string, string> = { created: "شروع پرداخت در حال بررسی", initiation_unknown: "نتیجهٔ شروع پرداخت نامشخص", redirected: "در انتظار تأیید درگاه", captured: "پرداخت تأییدشده", review_required: "وجه دریافت‌شده؛ نیازمند بررسی مالی", rejected: "درخواست درگاه رد شده" };
export function PaymentRecovery({ orderId, allowStart = false, admin = false, onUpdate }: { orderId?: number; allowStart?: boolean; admin?: boolean; onUpdate?: () => void }) {
  const [rows, setRows] = useState<Payment[]>([]); const [notice, setNotice] = useState("");
  const [loading, setLoading] = useState(false); const [busy, setBusy] = useState(false);
  const [status, setStatus] = useState(""); const [cursors, setCursors] = useState<(number | null)[]>([null]);
  const [next, setNext] = useState<number | null>(null); const [provider, setProvider] = useState<string | null>(null);
  const generation = useRef(0); const requestKey = useRef<string | null>(null);
  const before = cursors[cursors.length - 1];
  const base = admin ? "/api/v1/payments/finance/queue/" : `/api/v1/payments/orders/${orderId}/attempts/`;
  const load = useCallback(async () => {
    const current = ++generation.current; setLoading(true);
    try {
      const query = new URLSearchParams(); if (before) query.set("before", String(before)); if (admin && status) query.set("status", status);
      const response = await fetch(`${base}?${query}`, { cache: "no-store" }); if (!response.ok) throw new Error();
      const result = await response.json();
      if (current === generation.current) { setRows(result.payments); setNext(result.next_before); }
    } catch { if (current === generation.current) { setRows([]); setNext(null); setNotice("وضعیت پرداخت دریافت نشد؛ دوباره تلاش کنید."); } }
    finally { if (current === generation.current) setLoading(false); }
  }, [base, before, status, admin]);
  useEffect(() => { void load(); return () => { generation.current++; }; }, [load]);
  useEffect(() => {
    if (admin) return;
    let active = true;
    fetch("/api/v1/payments/methods/", { cache: "no-store" }).then(async (response) => {
      if (!response.ok) throw new Error(); const result = await response.json();
      if (active) setProvider(result.available[0]?.id ?? null);
    }).catch(() => { if (active) setProvider(null); });
    return () => { active = false; };
  }, [admin]);
  async function verify(row: Payment, reason?: string) {
    setBusy(true); setNotice("");
    try {
      const response = await apiRequest("POST", admin ? `/api/v1/payments/finance/${row.id}/verify/` : `/api/v1/payments/${row.id}/verify/`, admin ? { reason } : {});
      const result = await response.json();
      if (!response.ok) throw new Error(result.error === "verification_credentials_changed" ? "تنظیمات پذیرنده تغییر کرده؛ مسئول مالی باید تنظیمات اصلی را بررسی کند." : "پرداخت هنوز تأیید نشد؛ برای جلوگیری از برداشت تکراری، وضعیت همین پرداخت را پیگیری کنید.");
      setNotice(result.payment.status === "review_required" ? "وجه تأیید شد اما سفارش نیازمند بررسی مالی است؛ با پشتیبانی تماس بگیرید." : "نتیجهٔ پرداخت تأیید شد.");
      await load(); onUpdate?.();
    } catch (error) { setNotice(error instanceof Error ? error.message : "ارتباط با سرویس برقرار نشد."); }
    finally { setBusy(false); }
  }
  function resume(row: Payment) {
    const destination = paymentDestination(row.provider, row.checkout_url, window.location.origin);
    if (destination) window.location.assign(destination); else setNotice("نشانی درگاه معتبر نیست؛ با پشتیبانی تماس بگیرید.");
  }
  async function start() {
    if (!provider || !orderId) return; setBusy(true); setNotice("");
    requestKey.current ??= crypto.randomUUID();
    try {
      const response = await apiRequest("POST", "/api/v1/payments/initiate/", { order_id: orderId, provider, idempotency_key: requestKey.current });
      const result = await response.json();
      if (!response.ok) {
        if (result.error === "gateway_request_rejected") requestKey.current = null;
        throw new Error("شروع پرداخت تأیید نشد؛ ابتدا وضعیت پرداخت‌های همین سفارش را بررسی کنید.");
      }
      if (result.payment.status === "rejected") { requestKey.current = null; await load(); setNotice("درخواست قبلی رد شده است؛ می‌توانید دوباره تلاش کنید."); return; }
      if (["captured", "review_required"].includes(result.payment.status)) { await load(); onUpdate?.(); return; }
      resume(result.payment);
    } catch (error) { setNotice(error instanceof Error ? error.message : "ارتباط برقرار نشد."); await load(); }
    finally { setBusy(false); }
  }
  async function exportPage(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); const reason = String(new FormData(event.currentTarget).get("reason"));
    setBusy(true); setNotice("");
    try {
      const query = new URLSearchParams(); if (before) query.set("before", String(before)); if (status) query.set("status", status);
      const response = await apiRequest("POST", `/api/v1/payments/finance/queue/export/?${query}`, { reason });
      if (!response.ok || !response.headers.get("content-type")?.startsWith("text/csv")) throw new Error();
      const url = URL.createObjectURL(await response.blob());
      const link = document.createElement("a"); link.href = url; link.download = "payment-reconciliation-page.csv";
      document.body.appendChild(link); link.click(); link.remove(); setTimeout(() => URL.revokeObjectURL(url), 1000);
      setNotice("خروجی همین صفحه با ثبت دلیل آماده شد؛ وضعیت پرداخت‌ها تغییری نکرد. برای صفحات دیگر جداگانه خروجی بگیرید.");
    } catch { setNotice("خروجی مالی تهیه نشد؛ دسترسی و ارتباط را بررسی کنید."); }
    finally { setBusy(false); }
  }
  function staffAction(event: FormEvent<HTMLFormElement>, row: Payment) {
    event.preventDefault(); void verify(row, String(new FormData(event.currentTarget).get("reason")));
  }
  return <section className="admin-card"><h2>{admin ? "بررسی نتیجهٔ پرداخت‌های درگاه" : "وضعیت پرداخت سفارش"}</h2>
    {admin && <label>وضعیت<select value={status} disabled={busy || loading} onChange={(event) => { setStatus(event.target.value); setCursors([null]); }}><option value="">نیازمند پیگیری</option>{Object.entries(labels).map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></label>}
    {admin && <form className="admin-inline-form" onSubmit={exportPage}><label>دلیل دریافت خروجی مالی<input name="reason" required minLength={3} maxLength={500} /></label><button disabled={busy || loading}>دانلود CSV همین صفحه</button><p>این فایل بخشی از فهرست جاری است و جای گزارش بانکی یا تأیید پرداخت را نمی‌گیرد.</p></form>}
    <button disabled={busy || loading} onClick={() => void load()}>تازه‌سازی</button>{notice && <p role="status">{notice}</p>}
    {loading ? <p>در حال دریافت وضعیت…</p> : <><ul className="admin-list">{rows.map((row) => <li key={row.id}><h3>پرداخت #{row.id}{admin && ` · سفارش #${row.order_id}`}</h3><p>{labels[row.status] ?? row.status} · {row.amount_toman.toLocaleString("fa-IR")} تومان</p><p>دریافت تأییدشده: {row.captured_toman.toLocaleString("fa-IR")} · استرداد ثبت‌شده: {row.refunded_toman.toLocaleString("fa-IR")} تومان{row.receipt && ` · شناسهٔ تراکنش: ${row.receipt}`}</p>
      {row.needs_provider_reconciliation && <p>نتیجهٔ شروع پرداخت باید توسط مسئول مالی با سوابق درگاه تطبیق داده شود. <a href="/support/">پشتیبانی</a></p>}
      {row.status === "review_required" && <p>ارسال خودکار سفارش انجام نمی‌شود؛ مسئول مالی باید وضعیت وجه و سفارش را بررسی کند.</p>}
      {row.checkout_url && <button disabled={busy || loading} onClick={() => resume(row)}>ادامهٔ همین پرداخت</button>}
      {row.can_verify && (admin ? <form className="admin-inline-form" onSubmit={(event) => staffAction(event, row)}><label>دلیل بررسی<input name="reason" required minLength={3} maxLength={500} /></label><button disabled={busy || loading}>بررسی مجدد با درگاه</button></form> : <button disabled={busy || loading} onClick={() => void verify(row)}>بررسی نتیجهٔ پرداخت</button>)}
      {admin && <PaymentInvestigation attemptId={row.id} />}
    </li>)}</ul>{!rows.length && <p>پرداختی در این فهرست وجود ندارد.</p>}
    <button disabled={busy || loading || cursors.length === 1} onClick={() => setCursors((values) => values.slice(0, -1))}>صفحهٔ قبل</button><button disabled={busy || loading || !next} onClick={() => setCursors((values) => [...values, next])}>صفحهٔ بعد</button>
    {!admin && allowStart && provider && cursors.length === 1 && !next && rows.every((row) => row.status === "rejected") && <button disabled={busy || loading} onClick={() => void start()}>شروع پرداخت سفارش</button>}</>}
  </section>;
}
