"use client";
import { FormEvent, useCallback, useEffect, useState } from "react";
import { apiRequest } from "@/lib/api";
type Slot = { id: number; starts_at: string; ends_at: string; capacity: number; is_active: boolean; bookings: number; has_history: boolean };
function localTime(value?: string) { if (!value) return ""; const date = new Date(value); date.setMinutes(date.getMinutes() - date.getTimezoneOffset()); return date.toISOString().slice(0, 16); }
function SlotForm({ methodId, row, changed }: { methodId: number; row?: Slot; changed: () => void }) {
  const [busy, setBusy] = useState(false); const [notice, setNotice] = useState("");
  async function save(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); const form = event.currentTarget; const data = new FormData(form); setBusy(true);
    try { const response = await apiRequest(row ? "PATCH" : "POST", row ? `/api/v1/operations/delivery-slots/${row.id}/` : `/api/v1/operations/shipping-methods/${methodId}/slots/`, { starts_at: new Date(String(data.get("starts_at"))).toISOString(), ends_at: new Date(String(data.get("ends_at"))).toISOString(), capacity: Number(data.get("capacity")), is_active: data.get("is_active") === "on", reason: data.get("reason") }); if (!response.ok) throw new Error(); if (!row) form.reset(); setNotice("بازه ذخیره شد."); changed(); } catch { setNotice("ذخیره نشد؛ تاریخ، ظرفیت و رزروهای موجود را بررسی کنید."); } finally { setBusy(false); }
  }
  return <form className="admin-inline-form" onSubmit={save}><label>شروع (زمان محلی دستگاه)<input name="starts_at" type="datetime-local" required defaultValue={localTime(row?.starts_at)} readOnly={Boolean(row?.has_history)} /></label><label>پایان (زمان محلی دستگاه)<input name="ends_at" type="datetime-local" required defaultValue={localTime(row?.ends_at)} readOnly={Boolean(row?.has_history)} /></label><label>ظرفیت گروه‌های ارسال<input name="capacity" type="number" required min={Math.max(1, row?.bookings ?? 0)} max={10000} defaultValue={row?.capacity ?? 1} /></label><label><input name="is_active" type="checkbox" defaultChecked={row?.is_active ?? true} />فعال برای رزرو جدید</label><label>دلیل<input name="reason" required minLength={3} maxLength={500} /></label><button disabled={busy}>ذخیرهٔ بازه</button>{notice && <p role="status">{notice}</p>}</form>;
}
export function DeliverySlots({ methodId }: { methodId: number }) {
  const [rows, setRows] = useState<Slot[]>([]); const [notice, setNotice] = useState("");
  const load = useCallback(async () => { try { const response = await fetch(`/api/v1/operations/shipping-methods/${methodId}/slots/`); if (!response.ok) throw new Error(); setRows((await response.json()).slots); } catch { setNotice("بازه‌ها دریافت نشدند."); } }, [methodId]);
  useEffect(() => { void load(); }, [load]);
  return <section><h4>بازه‌های قابل رزرو</h4><p>بازهٔ آینده تا ۹۰ روز و به طول حداکثر یک روز تعریف کنید. ظرفیت برای هر گروه ارسال است؛ رزرو سفارش پرداخت‌نشده ظرفیت را می‌گیرد و لغو یا انقضا آن را آزاد می‌کند. تاریخ بازهٔ رزروشده قابل تغییر نیست. این تقویم اتصال به پیک ایجاد نمی‌کند.</p>{notice && <p role="status">{notice}</p>}<SlotForm methodId={methodId} changed={() => void load()} />{rows.map((row) => <details key={row.id}><summary>{new Date(row.starts_at).toLocaleString("fa-IR")} · {row.bookings}/{row.capacity} رزرو</summary><SlotForm key={JSON.stringify(row)} methodId={methodId} row={row} changed={() => void load()} /></details>)}</section>;
}
