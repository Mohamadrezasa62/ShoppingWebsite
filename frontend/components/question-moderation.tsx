"use client";
import { FormEvent, useCallback, useEffect, useState } from "react";
import { apiRequest } from "@/lib/api";
type Question = { id: number; product: string; body: string; answer: string };
export function QuestionModeration() {
  const [rows, setRows] = useState<Question[]>([]), [notice, setNotice] = useState(""), [busy, setBusy] = useState(false);
  const load = useCallback(async () => { try { const r = await fetch("/api/v1/operations/questions/"); if (!r.ok) throw new Error(); setRows((await r.json()).questions); } catch { setNotice("پرسش‌ها دریافت نشدند."); } }, []);
  useEffect(() => { void load(); }, [load]);
  async function decide(event: FormEvent<HTMLFormElement>, id: number) { event.preventDefault(); const data = new FormData(event.currentTarget); setBusy(true); try { const r = await apiRequest("POST", `/api/v1/operations/questions/${id}/decision/`, { status: data.get("status"), answer: data.get("answer"), reason: data.get("reason") }); if (!r.ok) throw new Error(); setNotice("تصمیم ثبت شد."); await load(); } catch { setNotice("تصمیم ثبت نشد؛ انتشار به پاسخ حداقل سه‌حرفی نیاز دارد."); } finally { setBusy(false); } }
  return <section className="admin-card"><h1>پرسش‌های محصول</h1>{notice && <p role="status">{notice}</p>}<ul className="admin-list">{rows.map(q => <li key={q.id}><h2>{q.product}</h2><p>{q.body}</p><form className="admin-inline-form" onSubmit={e => void decide(e, q.id)}><label>پاسخ<textarea name="answer" maxLength={4000} defaultValue={q.answer} /></label><label>تصمیم<select name="status"><option value="published">پاسخ و انتشار</option><option value="rejected">رد</option></select></label><label>دلیل<input name="reason" required minLength={3} maxLength={500} /></label><button disabled={busy}>ثبت تصمیم</button></form></li>)}</ul>{!rows.length && <p>پرسشی در انتظار بررسی نیست.</p>}</section>;
}
