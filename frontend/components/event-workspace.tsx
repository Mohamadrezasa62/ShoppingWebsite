"use client";
import { FormEvent, useCallback, useEffect, useState } from "react";
import { apiRequest } from "@/lib/api";
type Event = { id: number; topic: string; status: string; attempts: number; last_error: string; available_at: string };
type Summary = { status: string; count: number; oldest: string | null };
export function EventWorkspace() {
  const [events, setEvents] = useState<Event[]>([]), [summary, setSummary] = useState<Summary[]>([]), [notice, setNotice] = useState(""), [busy, setBusy] = useState(false);
  const load = useCallback(async () => { try { const response = await fetch("/api/v1/operations/events/"); if (!response.ok) throw new Error(); const data = await response.json(); setEvents(data.events); setSummary(data.summary); } catch { setNotice("وضعیت پردازش دریافت نشد."); } }, []);
  useEffect(() => { void load(); }, [load]);
  async function replay(e: FormEvent<HTMLFormElement>, id: number) { e.preventDefault(); const reason = new FormData(e.currentTarget).get("reason"); setBusy(true); try { const response = await apiRequest("POST", `/api/v1/operations/events/${id}/replay/`, { reason }); if (!response.ok) throw new Error(); setNotice("رویداد برای پردازش مجدد آماده شد."); await load(); } catch { setNotice("بازپردازش ثبت نشد."); } finally { setBusy(false); } }
  return <section className="admin-card"><h1>سلامت پردازش اعلان‌ها</h1><button onClick={() => void load()}>تازه‌سازی</button>{notice && <p role="status">{notice}</p>}<ul>{summary.map(s => <li key={s.status}>{s.status}: {s.count}</li>)}</ul><ul className="admin-list">{events.map(event => <li key={event.id}><strong>{event.topic} · {event.status}</strong><p>تعداد تلاش: {event.attempts} · {event.last_error}</p>{event.status === "dead" && <form className="admin-inline-form" onSubmit={e => void replay(e, event.id)}><label>دلیل پردازش مجدد<input name="reason" required minLength={3} maxLength={500} /></label><button disabled={busy}>پردازش مجدد پس از رفع خطا</button></form>}</li>)}</ul>{!events.length && <p>رویدادی در انتظار پردازش نیست.</p>}</section>;
}
