"use client";
import { FormEvent, useState } from "react";
import { apiRequest } from "@/lib/api";
export function CartCoupon({ code, reload }: { code: string; reload: () => Promise<void> }) {
  const [notice, setNotice] = useState(""); const [busy, setBusy] = useState(false);
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); setBusy(true); const data = new FormData(event.currentTarget);
    try { const response = await apiRequest("POST", "/api/v1/commerce/cart/coupon/", { code: data.get("code") }); if (!response.ok) throw new Error(); await reload(); setNotice("کوپن اعمال شد."); } catch { setNotice("کوپن معتبر یا قابل استفاده نیست."); } finally { setBusy(false); }
  }
  async function remove() { setBusy(true); try { const response = await apiRequest("DELETE", "/api/v1/commerce/cart/coupon/"); if (!response.ok) throw new Error(); await reload(); setNotice("کوپن حذف شد."); } catch { setNotice("حذف انجام نشد."); } finally { setBusy(false); } }
  return <section><form className="admin-inline-form" onSubmit={submit}><label>کد تخفیف<input name="code" required maxLength={64} /></label><button disabled={busy}>اعمال کد</button></form>{code && <p>{code} <button disabled={busy} onClick={() => void remove()}>حذف کد</button></p>}{notice && <p role="status">{notice}</p>}</section>;
}
