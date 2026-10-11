"use client";
import { FormEvent, useEffect, useState } from "react";
import { apiRequest } from "@/lib/api";
type Question = { id: number; body: string; answer: string };
export function ProductQuestions({ productId }: { productId: number }) {
  const [rows, setRows] = useState<Question[]>([]), [notice, setNotice] = useState(""), [busy, setBusy] = useState(false);
  useEffect(() => { let active = true; fetch(`/api/v1/catalog/questions/${productId}/`).then(async response => { if (!response.ok) throw new Error(); const data = await response.json(); if (active) setRows(data.questions); }).catch(() => { if (active) setNotice("پرسش‌ها دریافت نشدند."); }); return () => { active = false; }; }, [productId]);
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); const form = event.currentTarget; setBusy(true);
    try { const response = await apiRequest("POST", `/api/v1/catalog/questions/${productId}/`, { body: new FormData(form).get("body") }); if (!response.ok) { setNotice(response.status === 401 ? "ابتدا وارد حساب شوید." : response.status === 429 ? "سه پرسش شما در انتظار بررسی است." : "ثبت پرسش انجام نشد."); return; } form.reset(); setNotice("پرسش برای بررسی و پاسخ ثبت شد."); } catch { setNotice("ارتباط برقرار نشد."); } finally { setBusy(false); }
  }
  return <section className="admin-card seller-section"><h2>پرسش و پاسخ</h2>{notice && <p role="status">{notice}</p>}<ul className="admin-list">{rows.map(q => <li key={q.id}><h3>{q.body}</h3><p>پاسخ پشتیبانی: {q.answer}</p></li>)}</ul>{!rows.length && <p>هنوز پرسش پاسخ‌داده‌شده‌ای منتشر نشده است.</p>}<form onSubmit={submit} className="admin-inline-form"><label>پرسش دربارهٔ محصول<textarea name="body" required minLength={10} maxLength={2000} /></label><button disabled={busy}>ثبت پرسش</button></form></section>;
}
