"use client";
import { FormEvent, useCallback, useEffect, useState } from "react";
import { apiRequest } from "@/lib/api";

export function SellerRatingForm({ deliveryId }: { deliveryId: number }) {
  const [notice, setNotice] = useState(""); const [busy, setBusy] = useState(false);
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); setBusy(true); const data = new FormData(event.currentTarget);
    try {
      const response = await apiRequest("POST", "/api/v1/seller/reviews/", { delivery_id: deliveryId, rating: Number(data.get("rating")), body: data.get("body") });
      setNotice(response.ok ? "امتیاز ثبت شد و پس از بررسی منتشر می‌شود." : "ثبت انجام نشد؛ هر ارسال تحویل‌شده یک امتیاز دارد و فروشنده نمی‌تواند به فروشگاه خود امتیاز دهد.");
    } catch { setNotice("ارتباط برقرار نشد."); } finally { setBusy(false); }
  }
  return <details><summary>امتیاز به فروشنده</summary><form className="admin-inline-form" onSubmit={submit}><label>امتیاز<select name="rating">{[5, 4, 3, 2, 1].map((value) => <option key={value}>{value}</option>)}</select></label><label>تجربهٔ خرید<textarea name="body" required minLength={3} maxLength={2000} /></label><button disabled={busy}>ثبت امتیاز</button></form>{notice && <p role="status">{notice}</p>}</details>;
}

type Review = { id: number; seller: string; delivery_id?: number; rating: number; body: string; status: string };
const labels: Record<string, string> = { pending: "در انتظار بررسی", published: "منتشرشده", rejected: "ردشده" };
export function SellerReviewWorkspace({ admin = false }: { admin?: boolean }) {
  const [rows, setRows] = useState<Review[]>([]); const [status, setStatus] = useState("pending"); const [notice, setNotice] = useState(""); const [busy, setBusy] = useState(false);
  const load = useCallback(async () => {
    try { const response = await fetch(admin ? `/api/v1/operations/seller-reviews/?status=${status}` : "/api/v1/seller/reviews/"); if (!response.ok) throw new Error(); setRows((await response.json()).reviews); }
    catch { setNotice("امتیازها دریافت نشدند؛ دسترسی حساب را بررسی کنید."); }
  }, [admin, status]);
  useEffect(() => { void load(); }, [load]);
  async function decide(event: FormEvent<HTMLFormElement>, id: number) {
    event.preventDefault(); setBusy(true); const values = new FormData(event.currentTarget);
    try { const response = await apiRequest("POST", `/api/v1/operations/seller-reviews/${id}/decision/`, { status: values.get("status"), reason: values.get("reason") }); if (!response.ok) throw new Error(); await load(); }
    catch { setNotice("تصمیم ثبت نشد."); } finally { setBusy(false); }
  }
  return <section className="admin-card"><h2>{admin ? "بررسی امتیاز فروشندگان" : "امتیازهای من به فروشندگان"}</h2>{admin && <label>وضعیت<select value={status} onChange={(event) => setStatus(event.target.value)}>{Object.entries(labels).map(([key, value]) => <option key={key} value={key}>{value}</option>)}</select></label>}<button onClick={() => void load()}>تازه‌سازی</button>{notice && <p role="status">{notice}</p>}<ul className="admin-list">{rows.map((row) => <li key={row.id}><strong>{row.seller} · {row.rating}/۵</strong><p>{row.body}</p><p>{labels[row.status]}</p>{admin && <form className="admin-inline-form" onSubmit={(event) => void decide(event, row.id)}><label>تصمیم<select name="status">{Object.entries(labels).map(([key, value]) => <option key={key} value={key}>{value}</option>)}</select></label><label>دلیل<input name="reason" required minLength={3} maxLength={500} /></label><button disabled={busy}>ثبت تصمیم</button></form>}</li>)}</ul>{!rows.length && <p>امتیازی در این فهرست نیست.</p>}</section>;
}

export function PublicSellerReviews({ sellerId }: { sellerId: number }) {
  const [data, setData] = useState<{ seller: { name: string }; average_rating: number | null; count: number; reviews: { rating: number; body: string }[] } | null>(null);
  const [error, setError] = useState("");
  useEffect(() => {
    let current = true;
    fetch(`/api/v1/seller/public/${sellerId}/reviews/`).then(async (response) => { if (!response.ok) throw new Error(); const result = await response.json(); if (current) setData(result); }).catch(() => { if (current) setError("این فروشنده اکنون در دسترس نیست."); });
    return () => { current = false; };
  }, [sellerId]);
  return <section>{error ? <p role="alert">{error}</p> : !data ? <p>در حال بارگذاری...</p> : <><h1>{data.seller.name}</h1><p>{data.average_rating === null ? "هنوز امتیازی منتشر نشده است." : `${data.average_rating.toFixed(1)} از ۵ · ${data.count} نظر`}</p><p>این امتیازها از خریدهای تحویل‌شده و پس از بررسی منتشر شده‌اند.</p><ul className="admin-list">{data.reviews.map((row, index) => <li key={index}><strong>{row.rating}/۵ · خرید تأییدشده</strong><p>{row.body}</p></li>)}</ul></>}</section>;
}
