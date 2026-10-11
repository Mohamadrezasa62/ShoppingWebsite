"use client";
import { FormEvent, useCallback, useEffect, useRef, useState } from "react";
import { apiRequest, csrfToken } from "@/lib/api";
type Image = { id: number; alt_text: string; status: string; preview_url: string; product?: string; review_status?: string };
type Review = { id: number; product: string; title: string; body: string; status: string; images: Image[] };
const statuses: Record<string, string> = { pending: "در انتظار بررسی", approved: "تأییدشده", published: "منتشرشده", rejected: "ردشده" };

function UploadForm({ reviewId, changed }: { reviewId: number; changed: () => Promise<void> }) {
  const [busy, setBusy] = useState(false); const [notice, setNotice] = useState(""); const requestKey = useRef("");
  async function upload(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); setBusy(true); const form = event.currentTarget; const data = new FormData(form); const file = data.get("image");
    if (!(file instanceof File) || file.size === 0 || file.size > 5 * 1024 * 1024) { setNotice("تصویر باید حداکثر ۵ مگابایت باشد."); setBusy(false); return; }
    if (!requestKey.current) requestKey.current = crypto.randomUUID(); data.set("request_key", requestKey.current);
    try {
      await fetch("/api/v1/auth/csrf/", { credentials: "same-origin" });
      const response = await fetch(`/api/v1/catalog/my-reviews/${reviewId}/images/`, { method: "POST", credentials: "same-origin", headers: { "X-CSRFToken": csrfToken() ?? "" }, body: data });
      if (!response.ok) throw new Error();
      requestKey.current = ""; form.reset(); setNotice("تصویر ثبت شد و برای انتشار نیاز به تأیید دارد."); await changed();
    } catch { setNotice("بارگذاری انجام نشد؛ قالب تصویر، سقف سه تصویر و وضعیت نظر را بررسی کنید."); } finally { setBusy(false); }
  }
  return <form className="admin-inline-form" onSubmit={upload} onChange={() => { requestKey.current = ""; }}><label>تصویر<input type="file" name="image" accept="image/jpeg,image/png,image/webp" required disabled={busy} /></label><label>شرح تصویر<input name="alt_text" required maxLength={240} disabled={busy} /></label><button disabled={busy}>بارگذاری</button>{notice && <p role="status">{notice}</p>}</form>;
}

export function MyReviewImages() {
  const [reviews, setReviews] = useState<Review[]>([]); const [notice, setNotice] = useState(""); const [busy, setBusy] = useState(false);
  const load = useCallback(async () => { try { const response = await fetch("/api/v1/catalog/my-reviews/"); if (!response.ok) throw new Error(); setReviews((await response.json()).reviews); } catch { setNotice("نظرات دریافت نشدند؛ ابتدا وارد حساب شوید."); } }, []);
  useEffect(() => { void load(); }, [load]);
  async function withdraw(id: number) {
    setBusy(true);
    try { const response = await apiRequest("DELETE", `/api/v1/catalog/review-images/${id}/withdraw/`); if (!response.ok) throw new Error(); await load(); setNotice("تصویر از نمایش برداشته شد."); }
    catch { setNotice("برداشتن تصویر انجام نشد."); } finally { setBusy(false); }
  }
  return <section><h1>نظرات و تصاویر من</h1><p>پس از ثبت نظر در صفحهٔ محصول، حداکثر سه تصویر JPEG، PNG یا WebP اضافه کنید. هر تصویر تا ۵ مگابایت است و جدا از متن نظر بررسی می‌شود.</p>{notice && <p role="status">{notice}</p>}<ul className="admin-list">{reviews.map((review) => <li className="admin-card" key={review.id}><h2>{review.product}</h2><strong>{review.title}</strong><p>{review.body}</p><p>{statuses[review.status]}</p><div className="product-gallery">{review.images.map((image) => <figure key={image.id}><img src={image.preview_url} alt={image.alt_text} loading="lazy" /><figcaption>{image.alt_text} · {statuses[image.status]}</figcaption><button disabled={busy} onClick={() => void withdraw(image.id)}>برداشتن تصویر</button></figure>)}</div>{review.status !== "rejected" && <UploadForm reviewId={review.id} changed={load} />}</li>)}</ul>{!reviews.length && <p>هنوز نظری ثبت نکرده‌اید.</p>}</section>;
}

export function ReviewImageModeration() {
  const [images, setImages] = useState<Image[]>([]); const [status, setStatus] = useState("pending"); const [notice, setNotice] = useState(""); const [busy, setBusy] = useState(false);
  const load = useCallback(async () => { try { const response = await fetch(`/api/v1/operations/review-images/?status=${status}`); if (!response.ok) throw new Error(); setImages((await response.json()).images); } catch { setNotice("تصاویر دریافت نشدند."); } }, [status]);
  useEffect(() => { void load(); }, [load]);
  async function decide(event: FormEvent<HTMLFormElement>, id: number) {
    event.preventDefault(); setBusy(true); const data = new FormData(event.currentTarget);
    try { const response = await apiRequest("POST", `/api/v1/operations/review-images/${id}/decision/`, { status: data.get("status"), reason: data.get("reason") }); if (!response.ok) throw new Error(); await load(); }
    catch { setNotice("تصمیم ثبت نشد."); } finally { setBusy(false); }
  }
  return <section className="admin-card"><h2>بررسی تصاویر نظرات</h2><label>فهرست<select value={status} onChange={(event) => setStatus(event.target.value)}>{["pending", "approved", "rejected"].map((key) => <option key={key} value={key}>{statuses[key]}</option>)}</select></label><button onClick={() => void load()}>تازه‌سازی</button>{notice && <p role="status">{notice}</p>}<ul className="admin-list">{images.map((image) => <li key={image.id}><h3>{image.product}</h3><p>وضعیت متن نظر: {statuses[image.review_status ?? "pending"]}</p><div className="product-gallery"><img src={image.preview_url} alt={image.alt_text} loading="lazy" /></div><p>{image.alt_text}</p><form className="admin-inline-form" onSubmit={(event) => void decide(event, image.id)}><label>تصمیم<select name="status">{["approved", "rejected", "pending"].map((key) => <option key={key} value={key}>{statuses[key]}</option>)}</select></label><label>دلیل<input name="reason" required minLength={3} maxLength={500} /></label><button disabled={busy}>ثبت تصمیم</button></form></li>)}</ul>{!images.length && <p>تصویری در این فهرست نیست.</p>}</section>;
}
