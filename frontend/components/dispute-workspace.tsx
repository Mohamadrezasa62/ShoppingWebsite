"use client";

import { FormEvent, useCallback, useEffect, useState } from "react";
import { apiRequest } from "@/lib/api";

type Dispute = { id: number; order_id: number; seller: string; status: string; reason: string; seller_response: string; resolution: string; internal_note?: string };
const labels: Record<string, string> = { open: "در انتظار پاسخ", seller_responded: "فروشنده پاسخ داد", escalated: "ارجاع برای بررسی", resolved: "تعیین تکلیف شد", rejected: "رد شد" };

export function DisputeRequest({ deliveryId, status }: { deliveryId: number; status: string | null }) {
  const [notice, setNotice] = useState(""); const [busy, setBusy] = useState(false); const [submitted, setSubmitted] = useState(false);
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); const data = new FormData(event.currentTarget); setBusy(true);
    try {
      const response = await apiRequest("POST", "/api/v1/operations/my-disputes/", { delivery_id: deliveryId, reason: data.get("reason") });
      if (!response.ok) throw new Error(); setSubmitted(true); setNotice("اختلاف ثبت شد. نتیجه را در بخش اختلاف‌های سفارش ببینید.");
    } catch { setNotice("ثبت انجام نشد؛ درخواست قبلی یا وضعیت ارسال را بررسی کنید."); } finally { setBusy(false); }
  }
  return <div>{status || submitted ? <a href="/disputes/">پیگیری اختلاف ارسال</a> : <details><summary>ثبت اختلاف دربارهٔ این ارسال</summary><form className="admin-inline-form" onSubmit={submit}><label>شرح اختلاف<textarea name="reason" required minLength={3} maxLength={2000} /></label><button disabled={busy}>ثبت اختلاف</button></form></details>}{notice && <p role="status">{notice}</p>}</div>;
}

export function DisputeWorkspace({ admin = false, sellerId, canReview = false }: { admin?: boolean; sellerId?: number; canReview?: boolean }) {
  const [rows, setRows] = useState<Dispute[]>([]); const [notice, setNotice] = useState(""); const [busy, setBusy] = useState(false);
  const base = sellerId ? `/api/v1/seller/stores/${sellerId}/disputes/` : `/api/v1/operations/${admin ? "disputes" : "my-disputes"}/`;
  const load = useCallback(async () => {
    try { const response = await fetch(base, { credentials: "same-origin" }); if (!response.ok) throw new Error(); setRows((await response.json()).disputes); }
    catch { setNotice("اختلاف‌ها دریافت نشدند؛ ورود و دسترسی را بررسی کنید."); }
  }, [base]);
  useEffect(() => { void load(); }, [load]);
  async function submit(event: FormEvent<HTMLFormElement>, id: number) {
    event.preventDefault(); const data = new FormData(event.currentTarget); setBusy(true); setNotice("");
    try {
      const body = sellerId ? { dispute_id: id, body: data.get("body") } : { status: data.get("status"), reason: data.get("reason"), resolution: data.get("resolution"), internal_note: data.get("internal_note") };
      const response = await apiRequest("POST", sellerId ? base : `${base}${id}/decision/`, body);
      if (!response.ok) throw new Error(); await load(); setNotice("ثبت شد.");
    } catch { setNotice("ثبت انجام نشد؛ وضعیت و اطلاعات را بررسی کنید."); } finally { setBusy(false); }
  }
  return <section className="admin-card"><h2>اختلاف‌های سفارش</h2><p>تعیین تکلیف اختلاف به معنی انتقال پول یا استرداد خودکار نیست. اقدامات مالی از مسیر مالی مستقل انجام می‌شوند.</p>{notice && <p role="status">{notice}</p>}
    {!admin && !sellerId && <a href="/orders/">ثبت اختلاف از جزئیات سفارش</a>}
    <ul className="admin-list">{rows.map((row) => <li className="admin-record" key={row.id}><div><h3>اختلاف #{row.id} · سفارش #{row.order_id}</h3><p>{row.seller} · {labels[row.status]}</p><p>شرح مشتری: {row.reason}</p>{row.seller_response && <p>پاسخ فروشنده: {row.seller_response}</p>}{row.resolution && <p>نتیجهٔ بررسی: {row.resolution}</p>}{admin && row.internal_note && <p>یادداشت داخلی: {row.internal_note}</p>}</div>
      {sellerId && row.status === "open" && <form className="admin-inline-form" onSubmit={(event) => void submit(event, row.id)}><label>پاسخ فروشنده<textarea name="body" required minLength={3} maxLength={2000} /></label><button disabled={busy}>ثبت پاسخ</button></form>}
      {admin && canReview && ["open", "seller_responded", "escalated"].includes(row.status) && <form className="admin-inline-form" onSubmit={(event) => void submit(event, row.id)}><label>تصمیم<select name="status">{row.status !== "escalated" && <option value="escalated">ارجاع برای بررسی</option>}<option value="resolved">تعیین تکلیف</option><option value="rejected">رد اختلاف</option></select></label><label>نتیجهٔ قابل نمایش به طرفین<textarea name="resolution" required minLength={3} maxLength={1000} /></label><label>یادداشت داخلی<textarea name="internal_note" maxLength={1000} /></label><label>دلیل بررسی<input name="reason" required minLength={3} maxLength={500} /></label><button disabled={busy}>ثبت تصمیم</button></form>}
    </li>)}</ul>{rows.length === 0 && <p>اختلافی برای نمایش نیست.</p>}
  </section>;
}
