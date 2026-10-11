"use client";
import { FormEvent, useCallback, useEffect, useState } from "react";
import { apiRequest } from "@/lib/api";
type Coupon = { id: number; code: string; kind: string; value: number; is_active: boolean; usage_limit: number; budget_toman: number; budget_used_toman: number; starts_at: string; ends_at: string };
export function PromotionsWorkspace() {
  const [coupons, setCoupons] = useState<Coupon[]>([]); const [notice, setNotice] = useState(""); const [busy, setBusy] = useState(false);
  const load = useCallback(async () => { try { const response = await fetch("/api/v1/operations/coupons/"); if (!response.ok) throw new Error(); setCoupons((await response.json()).coupons); } catch { setNotice("کوپن‌ها دریافت نشدند."); } }, []);
  useEffect(() => { void load(); }, [load]);
  async function create(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); setBusy(true); const form = event.currentTarget; const data = new FormData(form);
    try {
      const response = await apiRequest("POST", "/api/v1/operations/coupons/", { code: data.get("code"), kind: data.get("kind"), value: Number(data.get("value")), min_subtotal_toman: Number(data.get("minimum")), max_discount_toman: Number(data.get("maximum")), budget_toman: Number(data.get("budget")), usage_limit: Number(data.get("limit")), per_user_limit: Number(data.get("per_user")), starts_at: new Date(String(data.get("start"))).toISOString(), ends_at: new Date(String(data.get("end"))).toISOString(), reason: data.get("reason") });
      if (!response.ok) throw new Error(); form.reset(); await load();
    } catch { setNotice("کوپن ثبت نشد؛ زمان، درصد و یکتا بودن کد را بررسی کنید."); } finally { setBusy(false); }
  }
  async function toggle(event: FormEvent<HTMLFormElement>, coupon: Coupon) {
    event.preventDefault(); setBusy(true); const data = new FormData(event.currentTarget);
    try { const response = await apiRequest("POST", `/api/v1/operations/coupons/${coupon.id}/status/`, { is_active: !coupon.is_active, reason: data.get("reason") }); if (!response.ok) throw new Error(); await load(); } catch { setNotice("وضعیت ثبت نشد."); } finally { setBusy(false); }
  }
  return <section className="admin-card"><h1>کوپن‌ها و تخفیف‌ها</h1>{notice && <p role="status">{notice}</p>}<form className="admin-inline-form" onSubmit={create}><label>کد<input name="code" required maxLength={64} pattern="[A-Za-z0-9_-]+" /></label><label>نوع<select name="kind"><option value="percent">درصدی</option><option value="fixed">مبلغ ثابت (تومان)</option></select></label><label>مقدار<input name="value" type="number" min={1} required /></label><label>حداقل سبد<input name="minimum" type="number" min={0} defaultValue={0} /></label><label>سقف تخفیف (۰: بدون سقف)<input name="maximum" type="number" min={0} defaultValue={0} /></label><label>بودجهٔ کل تخفیف (۰: بدون سقف)<input name="budget" type="number" min={0} defaultValue={0} /></label><label>ظرفیت کل<input name="limit" type="number" min={1} defaultValue={100} required /></label><label>ظرفیت هر مشتری<input name="per_user" type="number" min={1} defaultValue={1} required /></label><label>شروع (زمان دستگاه)<input name="start" type="datetime-local" required /></label><label>پایان (زمان دستگاه)<input name="end" type="datetime-local" required /></label><label>دلیل<input name="reason" required minLength={3} maxLength={500} /></label><button disabled={busy}>ساخت کوپن</button></form><ul className="admin-list">{coupons.map((coupon) => <li key={coupon.id}><strong>{coupon.code} · {coupon.value}{coupon.kind === "percent" ? "٪" : " تومان"}</strong><p>{coupon.is_active ? "فعال" : "غیرفعال"} · ظرفیت {coupon.usage_limit} · پایان {new Date(coupon.ends_at).toLocaleString("fa-IR")}</p><p>بودجهٔ مصرف‌شده یا رزرو: {coupon.budget_used_toman.toLocaleString("fa-IR")} تومان · سقف {coupon.budget_toman || "بدون محدودیت"}</p><form className="admin-inline-form" onSubmit={(event) => void toggle(event, coupon)}><label>دلیل<input name="reason" required minLength={3} maxLength={500} /></label><button disabled={busy}>{coupon.is_active ? "غیرفعال کردن" : "فعال کردن"}</button></form></li>)}</ul></section>;
}
