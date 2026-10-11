"use client";
import { PaymentRecovery } from "@/components/payment-recovery";
import { FormEvent, useCallback, useEffect, useState } from "react";
import { apiRequest } from "@/lib/api";
type Settlement = { id: number; seller_id: number; amount_toman: number; status: string; created_by: number };
type Entry = { id: number; order_id: number; kind: string; amount_toman: number; seller_id: number | null };
export function FinanceWorkspace() {
  const [entries, setEntries] = useState<Entry[]>([]); const [settlements, setSettlements] = useState<Settlement[]>([]);
  const [error, setError] = useState(""); const [busy, setBusy] = useState(false);
  const load = useCallback(async () => {
    try {
      const responses = await Promise.all([fetch("/api/v1/operations/transactions/"), fetch("/api/v1/operations/settlements/")]);
      if (responses.some((response) => !response.ok)) throw new Error();
      setEntries((await responses[0].json()).ledger); setSettlements((await responses[1].json()).settlements);
    } catch { setError("اطلاعات مالی دریافت نشدند."); }
  }, []);
  useEffect(() => { void load(); }, [load]);
  async function create(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); setBusy(true); setError("");
    const form = event.currentTarget; const data = new FormData(form);
    try {
      const response = await apiRequest("POST", "/api/v1/operations/settlements/", { seller_id: Number(data.get("seller")), idempotency_key: crypto.randomUUID(), reason: data.get("reason") });
      if (!response.ok) throw new Error();
      await load(); form.reset();
    } catch { setError("تسویه آماده نشد؛ فروشنده باید مطالبات تحویل‌شده و بدون مرجوعی باز داشته باشد."); } finally { setBusy(false); }
  }
  async function action(event: FormEvent<HTMLFormElement>, id: number) {
    event.preventDefault(); setBusy(true); setError(""); const data = new FormData(event.currentTarget);
    try {
      const response = await apiRequest("POST", `/api/v1/operations/settlements/${id}/action/`, { action: data.get("action"), reason: data.get("reason") });
      if (!response.ok) { const result = await response.json(); throw new Error(result.error === "second_approver_required" ? "تأییدکننده باید شخص دیگری باشد." : "ثبت انجام نشد؛ مرجوعی‌های باز، اصلاحات و وضعیت تسویه را بررسی کنید."); }
      await load();
    } catch (failure) { setError(failure instanceof Error ? failure.message : "ارتباط برقرار نشد."); } finally { setBusy(false); }
  }
  async function commission(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); setBusy(true); const data = new FormData(event.currentTarget);
    try {
      const response = await apiRequest("POST", `/api/v1/operations/sellers/${Number(data.get("seller"))}/commission/`, { commission_bps: Math.round(Number(data.get("percent")) * 100), reason: data.get("reason") });
      if (!response.ok) throw new Error();
      setError("نرخ برای سفارش‌های جدید ثبت شد.");
    } catch { setError("نرخ ثبت نشد."); } finally { setBusy(false); }
  }
  return <section className="admin-card"><h1>امور مالی</h1><PaymentRecovery admin /><p>کمیسیون روی مبلغ کالا اعمال می‌شود؛ ارسال فروشنده به مطالبات او اضافه می‌شود. انتقال بانکی فعال نیست.</p>{error && <p role="status">{error}</p>}
    <h2>نرخ کمیسیون فروشنده</h2><form className="admin-inline-form" onSubmit={commission}><label>شناسهٔ فروشنده<input name="seller" type="number" min={1} required /></label><label>درصد<input name="percent" type="number" min={0} max={100} step="0.01" required /></label><label>دلیل<input name="reason" required minLength={3} maxLength={500} /></label><button disabled={busy}>ثبت نرخ</button></form>
    <h2>آماده‌سازی تسویه</h2><form className="admin-inline-form" onSubmit={create}><label>شناسهٔ فروشنده<input name="seller" type="number" min={1} required /></label><label>دلیل<input name="reason" required minLength={3} maxLength={500} /></label><button disabled={busy}>آماده‌سازی</button></form>
    <ul className="admin-list">{settlements.map((row) => <li key={row.id}><strong>تسویه #{row.id} · فروشنده #{row.seller_id}</strong><p>{row.status} · {row.amount_toman.toLocaleString("fa-IR")} تومان</p>{["draft", "approved"].includes(row.status) && <form className="admin-inline-form" onSubmit={(event) => void action(event, row.id)}><label>عملیات<select name="action">{row.status === "draft" ? <option value="approve">تأیید توسط نفر دوم</option> : <option value="simulate_payout">شبیه‌سازی پرداخت؛ بدون انتقال پول</option>}<option value="cancel">لغو و آزادسازی برای محاسبهٔ مجدد</option></select></label><label>دلیل<input name="reason" required minLength={3} maxLength={500} /></label><button disabled={busy}>ثبت</button></form>}</li>)}</ul>
    <h2>آخرین ثبت‌های دفتر مالی</h2><ul className="admin-list">{entries.map((entry) => <li key={entry.id}>#{entry.id} · سفارش #{entry.order_id} · {entry.kind} · {entry.amount_toman.toLocaleString("fa-IR")} تومان</li>)}</ul>
  </section>;
}
