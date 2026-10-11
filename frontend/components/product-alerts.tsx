"use client";
import { FormEvent, useState } from "react";
import { apiRequest } from "@/lib/api";
export function ProductAlerts({ productId }: { productId: number }) {
  const [notice, setNotice] = useState(""), [busy, setBusy] = useState(false), [kind, setKind] = useState("back_in_stock");
  async function submit(event: FormEvent<HTMLFormElement>) { event.preventDefault(); const data = new FormData(event.currentTarget); setBusy(true); try { const response = await apiRequest("POST", "/api/v1/catalog/alerts/", { product_id: productId, kind, ...(kind === "price_drop" ? { target_price_toman: Number(data.get("price")) } : {}) }); setNotice(response.ok ? "اعلان یک‌باره در حساب شما ثبت شد." : response.status === 401 ? "ابتدا وارد حساب شوید." : "ثبت اعلان انجام نشد."); } catch { setNotice("ارتباط برقرار نشد."); } finally { setBusy(false); } }
  return <section className="seller-section"><h2>خبرم کن</h2><p>وقتی شرط شما برقرار شود، یک اعلان در حساب دریافت می‌کنید.</p>{notice && <p role="status">{notice}</p>}<form className="admin-inline-form" onSubmit={submit}><label>نوع اعلان<select value={kind} onChange={e => setKind(e.target.value)}><option value="back_in_stock">موجود شدن</option><option value="price_drop">قیمت به مبلغ دلخواه برسد</option></select></label>{kind === "price_drop" && <label>حداکثر قیمت به تومان<input name="price" type="number" required min={1} max={9000000000000000} /></label>}<button disabled={busy}>ثبت اعلان</button><a href="/alerts/">اعلان‌های محصول من</a></form></section>;
}
