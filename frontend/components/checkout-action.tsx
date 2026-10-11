"use client";
import { useEffect, useRef, useState } from "react";
import { paymentDestination } from "@/lib/payment-redirect";
import { apiRequest } from "@/lib/api";
type Method = { id: string; label: string; simulated: boolean };
export function CheckoutAction({ addressId, ready, quoteToken, refreshQuote, shippingMethods, shippingSlots }: { addressId: number; ready: boolean; quoteToken: string | null; refreshQuote: () => Promise<void>; shippingMethods: Record<string, number>; shippingSlots: Record<string, number> }) {
  const [methods, setMethods] = useState<Method[]>([]);
  const [notice, setNotice] = useState("");
  const [busy, setBusy] = useState(false);
  const key = useRef<string | null>(null);
  const pendingOrder = useRef<number | null>(null);
  const pendingMethods = useRef<string | null>(null);
  useEffect(() => { key.current = null; pendingOrder.current = null; pendingMethods.current = null; }, [addressId]);
  useEffect(() => { if (!pendingOrder.current) key.current = null; }, [quoteToken]);
  useEffect(() => {
    fetch("/api/v1/payments/methods/").then(async (response) => {
      if (!response.ok) throw new Error();
      setMethods((await response.json()).available);
    }).catch(() => setNotice("روش‌های پرداخت دریافت نشدند."));
  }, []);
  async function checkout() {
    if (!methods.length || !ready || !quoteToken || busy) return;
    setBusy(true); setNotice("");
    try {
      const selection = JSON.stringify([Object.entries(shippingMethods).sort(([a], [b]) => a.localeCompare(b)), Object.entries(shippingSlots).sort(([a], [b]) => a.localeCompare(b))]);
      if (pendingOrder.current && pendingMethods.current !== selection) throw new Error("سفارش قبلی با روش ارسال قبلی ثبت شده است؛ آن را در سفارش‌های من بررسی کنید.");
      key.current ??= crypto.randomUUID();
      if (!pendingOrder.current) {
        const response = await apiRequest("POST", "/api/v1/commerce/checkout/", { address_id: addressId, idempotency_key: key.current, quote_token: quoteToken, shipping_methods: shippingMethods, shipping_slots: shippingSlots });
        if (!response.ok) {
          const failure = await response.json();
          if (["quote_changed", "quote_expired", "invalid_quote"].includes(failure.error)) {
            await refreshQuote();
            throw new Error("برآورد تغییر کرده یا منقضی شده است؛ مبلغ و ارسال تازه را بررسی و دوباره تأیید کنید.");
          }
        }
        if (!response.ok) throw new Error("ثبت سفارش انجام نشد؛ قیمت، موجودی و نشانی را بررسی کنید.");
        pendingOrder.current = (await response.json()).order.id;
        pendingMethods.current = selection;
      }
      const response = await apiRequest("POST", "/api/v1/payments/initiate/", { order_id: pendingOrder.current, provider: methods[0].id, idempotency_key: key.current });
      if (!response.ok) throw new Error("سفارش ثبت شد؛ شروع پرداخت انجام نشد. سفارش در حساب شما قابل پیگیری است.");
      const payment = (await response.json()).payment;
      if (["captured", "review_required"].includes(payment.status)) { window.location.assign("/orders/"); return; }
      const destination = paymentDestination(payment.provider, payment.checkout_url, window.location.origin);
      if (!destination) throw new Error("نشانی پرداخت معتبر نیست.");
      window.location.assign(destination);
    } catch (error) { setNotice(error instanceof Error ? error.message : "ارتباط برقرار نشد؛ درخواست را دوباره امتحان کنید."); }
    finally { setBusy(false); }
  }
  return <div>{!methods.length ? <p>درگاه پرداخت هنوز فعال نشده است.</p> : <><p>{methods[0].label}</p><button className="catalog-action" disabled={!ready || !quoteToken || busy} onClick={() => void checkout()}>{busy ? "در حال ثبت..." : (methods[0].simulated ? "تأیید مبلغ و ادامهٔ پرداخت آزمایشی" : "تأیید مبلغ و ورود به درگاه پرداخت")}</button></>}{notice && <p role="alert">{notice} <a href="/orders/">سفارش‌های من</a></p>}</div>;
}
