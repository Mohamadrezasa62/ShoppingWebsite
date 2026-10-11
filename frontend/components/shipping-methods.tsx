"use client";
import { FormEvent, useCallback, useEffect, useState } from "react";
import { apiRequest } from "@/lib/api";
import { DeliverySlots } from "@/components/delivery-slots";
type Method = { id: number; code: string; label: string; fee_toman: number; min_days: number; max_days: number; is_active: boolean };
function MethodForm({ ruleId, row, changed }: { ruleId: number; row?: Method; changed: () => void }) {
  const [busy, setBusy] = useState(false); const [notice, setNotice] = useState("");
  async function save(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); const form = event.currentTarget; const data = new FormData(form); setBusy(true); setNotice("");
    try {
      const response = await apiRequest(row ? "PATCH" : "POST", row ? `/api/v1/operations/shipping-methods/${row.id}/` : `/api/v1/operations/shipping-rules/${ruleId}/methods/`, { code: data.get("code"), label: data.get("label"), fee_toman: Number(data.get("fee_toman")), min_days: Number(data.get("min_days")), max_days: Number(data.get("max_days")), is_active: data.get("is_active") === "on", reason: data.get("reason") });
      if (!response.ok) throw new Error(); if (!row) form.reset(); setNotice("روش ارسال ذخیره شد."); changed();
    } catch { setNotice("ذخیره نشد؛ کد یکتا، هزینه و بازهٔ روزها را بررسی کنید."); } finally { setBusy(false); }
  }
  return <form className="admin-inline-form" onSubmit={save}><label>کد روش<input name="code" required maxLength={80} pattern="[A-Za-z0-9_-]+" defaultValue={row?.code} /></label><label>نام روش<input name="label" required maxLength={160} defaultValue={row?.label} /></label><label>هزینهٔ کامل ارسال (تومان)<input name="fee_toman" type="number" required min={0} defaultValue={row?.fee_toman ?? 0} /></label><label>حداقل روز<input name="min_days" type="number" required min={0} max={365} defaultValue={row?.min_days ?? 1} /></label><label>حداکثر روز<input name="max_days" type="number" required min={0} max={365} defaultValue={row?.max_days ?? 2} /></label><label><input name="is_active" type="checkbox" defaultChecked={row?.is_active ?? true} />فعال</label><label>دلیل<input name="reason" required minLength={3} maxLength={500} /></label><button disabled={busy}>ذخیرهٔ روش ارسال</button>{notice && <p role="status">{notice}</p>}</form>;
}
export function ShippingMethods({ ruleId }: { ruleId: number }) {
  const [rows, setRows] = useState<Method[]>([]); const [notice, setNotice] = useState("");
  const load = useCallback(async () => { try { const response = await fetch(`/api/v1/operations/shipping-rules/${ruleId}/methods/`); if (!response.ok) throw new Error(); setRows((await response.json()).methods); } catch { setNotice("روش‌های ارسال دریافت نشدند."); } }, [ruleId]);
  useEffect(() => { void load(); }, [load]);
  return <section><h3>روش‌های قابل انتخاب مشتری</h3><p>ارسال معمولی از قانون اصلی استفاده می‌کند. حداکثر ۲۰ روش دیگر با هزینهٔ کامل و بازهٔ روز تعریف کنید. اتصال به پیک باید جداگانه انجام شود.</p>{notice && <p role="status">{notice}</p>}<MethodForm ruleId={ruleId} changed={() => void load()} />{rows.map((row) => <details key={row.id}><summary>{row.label} · {row.fee_toman.toLocaleString("fa-IR")} تومان</summary><MethodForm key={JSON.stringify(row)} ruleId={ruleId} row={row} changed={() => void load()} /><DeliverySlots methodId={row.id} /></details>)}</section>;
}
