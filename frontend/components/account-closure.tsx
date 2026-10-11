"use client";

import { useCallback, useEffect, useState, FormEvent } from "react";
import { apiRequest } from "@/lib/api";

type Closure = { id: number; status: string; reason: string; review_note: string; user_id?: number; blockers?: string[] };
const labels: Record<string, string> = { requested: "در انتظار بررسی", withdrawn: "انصراف داده‌شده", rejected: "ردشده", completed: "حساب بسته شد" };
const blockerLabels: Record<string, string> = { pending_payment: "سفارش پرداخت‌نشده", open_delivery: "ارسال باز", open_return: "مرجوعی باز", open_dispute: "اختلاف باز", open_cancellation: "لغو ارسال باز" };

export function AccountClosureWorkspace({ admin = false }: { admin?: boolean }) {
  const [rows, setRows] = useState<Closure[]>([]);
  const [blockers, setBlockers] = useState<string[]>([]);
  const [notice, setNotice] = useState("");
  const [busy, setBusy] = useState(false);
  const base = admin ? "/api/v1/operations/account-closures/" : "/api/v1/auth/closure-requests/";
  const load = useCallback(async () => {
    try {
      const response = await fetch(base, { credentials: "same-origin" });
      if (!response.ok) throw new Error();
      const data = await response.json(); setRows(data.requests); setBlockers(data.blockers ?? []);
    } catch { setNotice("دریافت درخواست‌ها انجام نشد."); }
  }, [base]);
  useEffect(() => { void load(); }, [load]);
  async function submit(path: string, body: Record<string, unknown>) {
    setBusy(true); setNotice("");
    try {
      const response = await apiRequest("POST", path, body);
      const data = await response.json();
      if (!response.ok) { setNotice(data.error === "closure_blocked" ? "ابتدا سفارش‌ها و درخواست‌های باز را تعیین تکلیف کنید؛ حساب کارکنان و فروشندگان به فرایند جدا نیاز دارد." : "ثبت انجام نشد؛ اطلاعات یا دسترسی را بررسی کنید."); return; }
      setNotice("ثبت شد."); await load();
    } catch { setNotice("ارتباط برقرار نشد."); } finally { setBusy(false); }
  }
  function request(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); const data = new FormData(event.currentTarget);
    void submit(base, { reason: data.get("reason") });
  }
  return <section className="admin-card"><h2>درخواست بستن حساب</h2>
    <p>پس از بررسی، ورود و استفاده از حساب غیرفعال می‌شود. سوابق هویتی، سفارش و پرداخت حفظ می‌شوند؛ این درخواست به معنی حذف داده‌ها نیست. برای حساب فروشنده یا کارکنان با پشتیبانی تماس بگیرید.</p>
    {blockers.length > 0 && <p>موارد نیازمند تعیین تکلیف: {blockers.map((key) => blockerLabels[key] ?? key).join("، ")}</p>}
    {!admin && !rows.some((row) => row.status === "requested") && <form className="admin-inline-form" onSubmit={request}><label>دلیل درخواست<textarea name="reason" minLength={3} maxLength={500} required /></label><label className="admin-check"><input type="checkbox" required /> پیامد بستن حساب و حفظ سوابق را خواندم.</label><button disabled={busy}>ثبت درخواست</button></form>}
    {notice && <p role="status">{notice}</p>}
    <ul className="admin-list">{rows.map((row) => <li className="admin-record" key={row.id}><div><strong>درخواست #{row.id} · {labels[row.status]}</strong>{admin && <p>کاربر #{row.user_id}</p>}<p>{row.reason}</p>{row.review_note && <p>{row.review_note}</p>}{row.blockers && row.blockers.length > 0 && <p>{row.blockers.map((key) => blockerLabels[key] ?? key).join("، ")}</p>}</div>
      {row.status === "requested" && (admin ? <form className="admin-inline-form" onSubmit={(event) => { event.preventDefault(); const data = new FormData(event.currentTarget); void submit(`${base}${row.id}/decision/`, { status: data.get("status"), reason: data.get("reason") }); }}><label>تصمیم<select name="status"><option value="rejected">رد درخواست</option><option value="completed">بستن حساب</option></select></label><label>دلیل بررسی<input name="reason" required minLength={3} maxLength={500} /></label><button disabled={busy}>ثبت تصمیم</button></form> : <button disabled={busy} onClick={() => void submit(`${base}${row.id}/withdraw/`, {})}>انصراف از درخواست</button>)}
    </li>)}</ul>
  </section>;
}
