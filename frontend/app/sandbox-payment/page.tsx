"use client";
import { useEffect, useState } from "react";
import { apiRequest } from "@/lib/api";
type Payment = { id: number; order_id: number; amount_toman: number; status: string; simulated: boolean };
export default function SandboxPaymentPage() {
  const [payment, setPayment] = useState<Payment | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  useEffect(() => {
    const id = new URLSearchParams(window.location.search).get("attempt");
    if (!id || !/^\d+$/.test(id)) { setError("شناسهٔ پرداخت معتبر نیست."); return; }
    fetch(`/api/v1/payments/${id}/`).then(async (response) => {
      if (!response.ok) throw new Error();
      const value = (await response.json()).payment;
      if (!value.simulated) throw new Error();
      setPayment(value);
    }).catch(() => setError("پرداخت آزمایشی در دسترس نیست. وارد حساب شوید."));
  }, []);
  async function result(outcome: string) {
    if (!payment) return; setBusy(true); setError("");
    try {
      const response = await apiRequest("POST", `/api/v1/payments/${payment.id}/sandbox-result/`, { outcome });
      if (!response.ok) throw new Error();
      setPayment((await response.json()).payment);
    } catch { setError("ثبت نتیجه انجام نشد؛ ممکن است حالت آزمایشی غیرفعال یا سفارش منقضی شده باشد."); }
    finally { setBusy(false); }
  }
  return <main className="form-page"><section className="form-card"><h1>شبیه‌سازی پرداخت</h1><p role="note">این صفحه فقط برای توسعه است؛ هیچ پولی انتقال داده نمی‌شود.</p>{error && <p role="alert">{error}</p>}{payment && <><p>سفارش #{payment.order_id} · {payment.amount_toman.toLocaleString("fa-IR")} تومان</p><p>نتیجه: {payment.status}</p>{payment.status === "redirected" && <div className="cart-actions"><button disabled={busy} onClick={() => void result("success")}>شبیه‌سازی موفقیت</button><button disabled={busy} onClick={() => void result("rejected")}>شبیه‌سازی رد پرداخت</button></div>}</>}<a href="/orders/">سفارش‌های من</a></section></main>;
}
