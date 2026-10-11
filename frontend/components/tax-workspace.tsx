"use client";
import { FormEvent, useEffect, useState } from "react";
import { apiRequest } from "@/lib/api";
type Rule = { category_id: number; label: string; rate_bps: number; is_active: boolean };
export function TaxWorkspace() {
  const [categories, setCategories] = useState<{id: number; name: string}[]>([]);
  const [category, setCategory] = useState("");
  const [rule, setRule] = useState<Rule | null>(null);
  const [notice, setNotice] = useState("");
  const [busy, setBusy] = useState(false);
  useEffect(() => {
    const controller = new AbortController();
    fetch("/api/v1/operations/categories/", {signal: controller.signal}).then(async r => { if (!r.ok) throw new Error(); return r.json(); }).then(d => setCategories(d.categories)).catch(() => { if (!controller.signal.aborted) setNotice("دسته‌ها دریافت نشدند."); });
    return () => controller.abort();
  }, []);
  useEffect(() => {
    setRule(null); setNotice("");
    if (!category) return;
    const controller = new AbortController();
    fetch(`/api/v1/operations/categories/${category}/tax/`, {signal: controller.signal}).then(async r => { if (!r.ok) throw new Error(); return r.json(); }).then(d => { if (!controller.signal.aborted) setRule(d.rule); }).catch(() => { if (!controller.signal.aborted) setNotice("تنظیم مالیات دریافت نشد."); });
    return () => controller.abort();
  }, [category]);
  async function save(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); if (!rule) return;
    const data = new FormData(event.currentTarget); const selected = category;
    setBusy(true); setNotice("");
    try {
      const response = await apiRequest("PUT", `/api/v1/operations/categories/${selected}/tax/`, { label: data.get("label"), rate_bps: Number(data.get("rate_bps")), is_active: data.get("is_active") === "on", reason: data.get("reason") });
      if (!response.ok) throw new Error();
      const updated = await response.json(); setRule(updated.rule); setNotice("تنظیم ثبت شد؛ سفارش‌های قبلی تغییر نمی‌کنند.");
    } catch { setNotice("ذخیره نشد؛ نقش، نرخ و دلیل تغییر را بررسی کنید."); } finally { setBusy(false); }
  }
  return <section className="admin-card"><h1>مالیات دسته‌ها</h1><p>قیمت کالا بدون مالیات است. نرخ فقط روی دستهٔ انتخابی و خالص کالا پس از تخفیف اعمال می‌شود؛ دستهٔ والد و هزینهٔ ارسال مشمول این تنظیم نیستند. بدون تنظیم فعال، مالیات صفر است.</p><p>نرخ را براساس سیاست تأییدشده ثبت کنید. این پنل نرخ قانونی یا صورتحساب مالیاتی تعیین نمی‌کند.</p><label>دسته<select disabled={busy} value={category} onChange={e => setCategory(e.target.value)}><option value="">انتخاب دسته</option>{categories.map(c => <option key={c.id} value={c.id}>{c.name}</option>)}</select></label>{rule && <form key={JSON.stringify(rule)} className="admin-inline-form" onSubmit={save}><label>عنوان مالیات<input name="label" required maxLength={160} defaultValue={rule.label} /></label><label>نرخ به صدم درصد (۱۰۰ یعنی ۱٪)<input name="rate_bps" required type="number" min={0} max={10000} step={1} defaultValue={rule.rate_bps} /></label><label><input name="is_active" type="checkbox" defaultChecked={rule.is_active} />فعال</label><label>دلیل تغییر<input name="reason" required minLength={3} maxLength={500} /></label><button disabled={busy}>ذخیرهٔ تنظیم</button></form>}{notice && <p role="status">{notice}</p>}</section>;
}
