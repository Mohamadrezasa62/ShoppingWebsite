"use client";
import { FormEvent, useCallback, useEffect, useState } from "react";
import { apiRequest } from "@/lib/api";
type Review = { id: number; product: string; title: string; body: string; rating: number };
export function ReviewModeration() {
  const [reviews, setReviews] = useState<Review[]>([]);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const load = useCallback(async () => {
    try {
      const response = await fetch("/api/v1/operations/reviews/");
      if (!response.ok) throw new Error();
      setReviews((await response.json()).reviews);
    } catch { setError("نظرات دریافت نشدند."); }
  }, []);
  useEffect(() => { void load(); }, [load]);
  async function decide(event: FormEvent<HTMLFormElement>, id: number) {
    event.preventDefault(); setBusy(true);
    const data = new FormData(event.currentTarget);
    try {
      const response = await apiRequest("POST", `/api/v1/operations/reviews/${id}/decision/`, { status: data.get("status"), reason: data.get("reason") });
      if (!response.ok) throw new Error();
      await load();
    } catch { setError("تصمیم ثبت نشد."); } finally { setBusy(false); }
  }
  return <section className="admin-card"><h1>بررسی نظرات</h1>{error && <p role="alert">{error}</p>}<ul className="admin-list">{reviews.map((review) => <li key={review.id}><h2>{review.product} · {review.rating}/۵</h2><strong>{review.title}</strong><p>{review.body}</p><form className="admin-inline-form" onSubmit={(event) => void decide(event, review.id)}><label>تصمیم<select name="status"><option value="published">انتشار</option><option value="rejected">رد</option></select></label><label>دلیل<input name="reason" required minLength={3} maxLength={500} /></label><button disabled={busy}>ثبت تصمیم</button></form></li>)}</ul>{!reviews.length && <p>نظری در انتظار بررسی نیست.</p>}</section>;
}
