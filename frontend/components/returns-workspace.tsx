"use client";
import { FormEvent, useCallback, useEffect, useState } from "react";
import { apiRequest } from "@/lib/api";
type ReturnCase = { id: number; order_id: number; delivery_id: number; reason: string; status: string; amount_toman: number; lines: { order_line_id: number; quantity: number; tax_amount_toman: number }[] };

export function ReturnRequest({ deliveryId, lineId, maximum }: { deliveryId: number; lineId: number; maximum: number }) {
  const [notice, setNotice] = useState(""); const [busy, setBusy] = useState(false);
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); setBusy(true);
    const form = event.currentTarget; const data = new FormData(form);
    try {
      const response = await apiRequest("POST", `/api/v1/commerce/deliveries/${deliveryId}/returns/`, { line_id: lineId, quantity: Number(data.get("quantity")), reason: data.get("reason") });
      if (!response.ok) throw new Error();
      setNotice("درخواست ثبت شد؛ وضعیت را در بخش مرجوعی‌ها دنبال کنید."); form.reset();
    } catch { setNotice("ثبت مرجوعی انجام نشد؛ تعداد و درخواست‌های قبلی را بررسی کنید."); } finally { setBusy(false); }
  }
  return <details><summary>درخواست مرجوعی</summary><form className="admin-inline-form" onSubmit={submit}><label>تعداد<input name="quantity" type="number" min={1} max={maximum} defaultValue={1} required /></label><label>دلیل<textarea name="reason" required minLength={3} maxLength={2000} /></label><button disabled={busy}>ثبت درخواست</button></form>{notice && <p role="status">{notice}</p>}</details>;
}

export function ReturnsWorkspace({ admin = false, canRefund = false }: { admin?: boolean; canRefund?: boolean }) {
  const [cases, setCases] = useState<ReturnCase[]>([]); const [error, setError] = useState(""); const [busy, setBusy] = useState(false);
  const load = useCallback(async () => {
    try {
      const response = await fetch(`/api/v1/${admin ? "operations" : "commerce"}/returns/`);
      if (!response.ok) throw new Error();
      setCases((await response.json()).returns);
    } catch { setError("مرجوعی‌ها دریافت نشدند؛ دسترسی حساب را بررسی کنید."); }
  }, [admin]);
  useEffect(() => { void load(); }, [load]);
  async function action(event: FormEvent<HTMLFormElement>, item: ReturnCase, refund: boolean) {
    event.preventDefault(); setBusy(true); setError("");
    const data = new FormData(event.currentTarget);
    try {
      const response = await apiRequest("POST", `/api/v1/operations/returns/${item.id}/${refund ? "sandbox-refund" : "decision"}/`, refund ? { reason: data.get("reason") } : { status: data.get("status"), reason: data.get("reason"), restock: data.get("restock") === "on" });
      if (!response.ok) throw new Error();
      await load();
    } catch { setError("تغییر ثبت نشد؛ وضعیت، نقش و فعال بودن حالت آزمایشی را بررسی کنید."); } finally { setBusy(false); }
  }
  const choices: Record<string, string[]> = { requested: ["approved", "rejected"], approved: ["received"], received: ["refund_pending"] };
  return <section className="admin-card"><h1>مرجوعی‌ها</h1>{error && <p role="alert">{error}</p>}<ul className="admin-list">{cases.map((item) => <li key={item.id}><strong>مرجوعی #{item.id} · سفارش #{item.order_id}</strong><p>{item.status} · {item.amount_toman.toLocaleString("fa-IR")} تومان</p><p>{item.reason}</p><p>{item.lines.map((line) => `قلم #${line.order_line_id}: ${line.quantity} عدد · سهم مالیات: ${line.tax_amount_toman.toLocaleString("fa-IR")} تومان`).join(" · ")}</p>
    {admin && choices[item.status] && <form className="admin-inline-form" onSubmit={(event) => void action(event, item, false)}><label>تصمیم<select name="status">{choices[item.status].map((value) => <option key={value}>{value}</option>)}</select></label>{item.status === "approved" && <label><input name="restock" type="checkbox" />پس از بررسی، کالا سالم و قابل فروش است</label>}<label>دلیل<input name="reason" required minLength={3} maxLength={500} /></label><button disabled={busy}>ثبت</button></form>}
    {admin && canRefund && ["received", "refund_pending"].includes(item.status) && <form className="admin-inline-form" onSubmit={(event) => void action(event, item, true)}><p>استرداد زیر فقط شبیه‌سازی توسعه است.</p><label>دلیل<input name="reason" required minLength={3} maxLength={500} /></label><button disabled={busy}>استرداد آزمایشی</button></form>}
    </li>)}</ul>{!cases.length && !error && <p>درخواستی ثبت نشده است.</p>}</section>;
}
