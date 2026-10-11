"use client";
import { FormEvent, useCallback, useEffect, useState } from "react";
import { apiRequest } from "@/lib/api";
type Campaign = { id: number; title: string; status: string; recipient_limit: number; reserved: number; delivered: number; skipped: number };

export function NotificationPreferences() {
  const [ready, setReady] = useState(false); const [enabled, setEnabled] = useState(false); const [notice, setNotice] = useState(""); const [busy, setBusy] = useState(false);
  useEffect(() => { fetch("/api/v1/operations/notification-preferences/").then(async (response) => { if (!response.ok) throw new Error(); setEnabled((await response.json()).marketing_in_app); setReady(true); }).catch(() => setNotice("تنظیمات اعلان دریافت نشد.")); }, []);
  async function save(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); setBusy(true);
    try { const response = await apiRequest("PATCH", "/api/v1/operations/notification-preferences/", { marketing_in_app: enabled }); if (!response.ok) throw new Error(); setNotice("انتخاب شما ذخیره شد."); }
    catch { setNotice("تنظیمات ذخیره نشد."); } finally { setBusy(false); }
  }
  return <section className="admin-card"><h2>تنظیمات اعلان</h2><p>اعلان‌های سفارش و پشتیبانی فعال می‌مانند. انتخاب زیر فقط پیام‌های بازاریابی داخل حساب را کنترل می‌کند و شامل SMS، ایمیل یا پوش نیست.</p><form onSubmit={save}><label className="admin-check"><input type="checkbox" disabled={!ready || busy} checked={enabled} onChange={(event) => setEnabled(event.target.checked)} /> با دریافت پیام‌های بازاریابی داخل حساب موافقم؛ هر زمان می‌توانم لغو کنم.</label><button disabled={busy || !ready}>ذخیرهٔ انتخاب</button></form>{notice && <p role="status">{notice}</p>}</section>;
}

export function CampaignWorkspace() {
  const [rows, setRows] = useState<Campaign[]>([]); const [notice, setNotice] = useState(""); const [busy, setBusy] = useState(false);
  const load = useCallback(async () => { try { const response = await fetch("/api/v1/operations/campaigns/"); if (!response.ok) throw new Error(); setRows((await response.json()).campaigns); } catch { setNotice("کمپین‌ها دریافت نشدند."); } }, []);
  useEffect(() => { void load(); }, [load]);
  async function create(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); const form = event.currentTarget; const data = new FormData(form); setBusy(true);
    try {
      const response = await apiRequest("POST", "/api/v1/operations/campaigns/", { title: data.get("title"), body: data.get("body"), link: data.get("link"), recipient_limit: Number(data.get("limit")), starts_at: new Date(String(data.get("start"))).toISOString(), ends_at: new Date(String(data.get("end"))).toISOString(), reason: data.get("reason") });
      if (!response.ok) throw new Error(); form.reset(); await load();
    } catch { setNotice("کمپین ثبت نشد؛ نشانی مقصد، زمان و ظرفیت را بررسی کنید."); } finally { setBusy(false); }
  }
  async function action(event: FormEvent<HTMLFormElement>, row: Campaign) {
    event.preventDefault(); const data = new FormData(event.currentTarget); setBusy(true);
    try { const response = await apiRequest("POST", `/api/v1/operations/campaigns/${row.id}/action/`, { action: data.get("action"), reason: data.get("reason") }); if (!response.ok) throw new Error(); await load(); }
    catch { setNotice("عملیات انجام نشد؛ وضعیت کمپین را بررسی کنید."); } finally { setBusy(false); }
  }
  return <section className="admin-card"><h2>کمپین اعلان داخل حساب</h2><p>پیام فقط برای مشتریان فعالِ دارای رضایت ارسال می‌شود. لغو رضایت پیش از تحویل، پیامِ در صف را متوقف می‌کند. پردازش پس‌زمینه باید فعال باشد؛ سقف مخاطب شامل پیام‌های کنارگذاشته‌شده نیز هست.</p>{notice && <p role="status">{notice}</p>}
    <form className="admin-inline-form" onSubmit={create}><label>عنوان<input name="title" required minLength={3} maxLength={200} /></label><label>متن<textarea name="body" required minLength={3} maxLength={2000} /></label><label>نشانی صفحهٔ محصول، مجموعه یا محتوا<input name="link" required maxLength={500} placeholder="/collections/summer/" /></label><label>سقف مخاطب<input name="limit" type="number" required min={1} max={10000} defaultValue={100} /></label><label>شروع (زمان دستگاه)<input name="start" type="datetime-local" required /></label><label>پایان (زمان دستگاه)<input name="end" type="datetime-local" required /></label><label>دلیل<input name="reason" required minLength={3} maxLength={500} /></label><button disabled={busy}>ساخت پیش‌نویس</button></form>
    <button type="button" disabled={busy} onClick={() => void load()}>به‌روزرسانی وضعیت</button>
    <ul className="admin-list">{rows.map((row) => <li className="admin-record" key={row.id}><div><h3>{row.title}</h3><p>{row.status} · ظرفیت {row.recipient_limit} · رزرو {row.reserved} · تحویل {row.delivered} · کنارگذاشته {row.skipped}</p></div>{row.status !== "cancelled" && <form className="admin-inline-form" onSubmit={(event) => void action(event, row)}><label>عملیات<select name="action">{row.status === "draft" && <option value="launch">شروع پردازش</option>}<option value="cancel">لغو ادامهٔ ارسال</option></select></label><label>دلیل<input name="reason" required minLength={3} maxLength={500} /></label><button disabled={busy}>ثبت</button></form>}</li>)}</ul>
  </section>;
}
