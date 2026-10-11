"use client";
import { FormEvent, useCallback, useEffect, useState } from "react";
import { apiRequest } from "@/lib/api";
import { RelatedProducts } from "@/components/related-products";
import { ProductAlerts } from "@/components/product-alerts";
import { ProductQuestions } from "@/components/product-questions";
type Review = { id: number; rating: number; title: string; body: string; verified_purchase: boolean; images: { url: string; alt: string }[] };

export function ProductTrust({ productId }: { productId: number }) {
  const [reviews, setReviews] = useState<Review[]>([]);
  const [average, setAverage] = useState<number | null>(null);
  const [count, setCount] = useState(0);
  const [notice, setNotice] = useState("");
  const [busy, setBusy] = useState(false);
  const load = useCallback(async () => {
    try {
      const response = await fetch(`/api/v1/catalog/reviews/${productId}/`);
      if (!response.ok) throw new Error();
      const data = await response.json(); setReviews(data.reviews); setAverage(data.average_rating); setCount(data.count);
    } catch { setNotice("نظرات بارگذاری نشدند."); }
  }, [productId]);
  useEffect(() => { void load(); }, [load]);
  async function save() {
    setBusy(true);
    try {
      const response = await apiRequest("POST", "/api/v1/catalog/wishlist/", { product_id: productId });
      setNotice(response.ok ? "به علاقه‌مندی‌ها اضافه شد." : response.status === 401 ? "ابتدا وارد حساب شوید." : "ذخیره انجام نشد.");
    } catch { setNotice("ارتباط برقرار نشد."); } finally { setBusy(false); }
  }
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); setBusy(true);
    const form = event.currentTarget; const values = new FormData(form);
    try {
      const response = await apiRequest("POST", `/api/v1/catalog/reviews/${productId}/`, { rating: Number(values.get("rating")), title: values.get("title"), body: values.get("body") });
      if (!response.ok) { setNotice(response.status === 401 ? "ابتدا وارد شوید." : "ثبت نظر به خرید تحویل‌شده نیاز دارد؛ برای هر محصول یک نظر مجاز است."); return; }
      form.reset(); setNotice("نظر ثبت شد و پس از بررسی منتشر می‌شود.");
    } catch { setNotice("ثبت نظر انجام نشد."); } finally { setBusy(false); }
  }
  return <section className="admin-card seller-section"><button disabled={busy} onClick={() => void save()}>افزودن به علاقه‌مندی‌ها</button><a href="/wishlist/"> علاقه‌مندی‌های من</a><a href="/my-reviews/"> نظرات و تصاویر من</a><h2>نظرات خریداران</h2><p>{average === null ? "هنوز نظری منتشر نشده است." : `${average.toFixed(1)} از ۵ · ${count} نظر`}</p>{notice && <p role="status">{notice}</p>}<ul className="admin-list">{reviews.map((review) => <li key={review.id}><strong>{review.title} · {review.rating}/۵</strong>{review.verified_purchase && <span> · خریدار تأییدشده</span>}<p>{review.body}</p><div className="product-gallery">{review.images?.map((image) => <img key={image.url} src={image.url} alt={image.alt} loading="lazy" />)}</div></li>)}</ul><form className="admin-inline-form" onSubmit={submit}><label>امتیاز<select name="rating" defaultValue="5">{[5, 4, 3, 2, 1].map((value) => <option key={value}>{value}</option>)}</select></label><label>عنوان<input name="title" required maxLength={160} /></label><label>نظر<textarea name="body" required maxLength={5000} /></label><button disabled={busy}>ثبت نظر</button></form><RelatedProducts productId={productId} /><ProductAlerts productId={productId} /><ProductQuestions productId={productId} /></section>;
}
