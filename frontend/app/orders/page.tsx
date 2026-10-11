"use client";

import { PaymentRecovery } from "@/components/payment-recovery";
import { useEffect, useState } from "react";
import { SellerRatingForm } from "@/components/seller-reviews";
import { DisputeRequest } from "@/components/dispute-workspace";
import { apiRequest } from "@/lib/api";
import { CancellationRequest } from "@/components/cancellation-workspace";
import { ReturnRequest } from "@/components/returns-workspace";

type Summary = { id: number; status: string; grand_total_toman: number; created_at: string };
type Order = Summary & { tax_total_toman: number; address: { full_name: string; province: string; city: string; street: string }; deliveries: { shipping_method_label: string; delivery_window_start: string | null; delivery_window_end: string | null; id: number; seller: string; status: string; cancellation_status: string|null; dispute_status: string|null; tracking_code: string; lines: { id: number; product_title: string; quantity: number; line_total_toman: number; discount_toman: number; tax_toman: number; tax_label: string }[] }[] };
const labels: Record<string, string> = { pending_payment: "در انتظار پرداخت", expired: "مهلت پرداخت پایان یافته", paid: "پرداخت‌شده", cancelled: "لغوشده", awaiting_fulfillment: "در انتظار آماده‌سازی", packing: "در حال بسته‌بندی", shipped: "ارسال‌شده", delivered: "تحویل‌شده" };

export default function OrdersPage() {
  const [orders, setOrders] = useState<Summary[]>([]);
  const [selected, setSelected] = useState<Order | null>(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [signedOut, setSignedOut] = useState(false);
  async function load() {
    try {
      const response = await fetch("/api/v1/commerce/orders/", { credentials: "same-origin" });
      if (response.status === 401) { setSignedOut(true); return; }
      if (!response.ok) throw new Error();
      setOrders((await response.json()).orders);
    } catch { setError("سفارش‌ها بارگذاری نشدند."); } finally { setLoading(false); }
  }
  useEffect(() => { void load(); }, []);
  async function detail(id: number) {
    setBusy(true); setError("");
    try {
      const response = await fetch(`/api/v1/commerce/orders/${id}/`);
      if (!response.ok) throw new Error();
      setSelected((await response.json()).order);
    } catch { setError("جزئیات سفارش دریافت نشد."); } finally { setBusy(false); }
  }
  async function cancel(id: number) {
    if (!window.confirm("سفارش پرداخت‌نشده لغو شود؟")) return;
    setBusy(true); setError("");
    try {
      const response = await apiRequest("POST", `/api/v1/commerce/orders/${id}/cancel/`);
      if (!response.ok) throw new Error();
      setSelected((await response.json()).order); await load();
    } catch { setError("لغو انجام نشد؛ وضعیت سفارش ممکن است تغییر کرده باشد."); } finally { setBusy(false); }
  }
  return <main className="catalog-main"><a className="brand" href="/account/">حساب کاربری</a><h1>سفارش‌های من</h1><a href="/seller-reviews/">امتیازهای فروشندگان</a><a href="/returns/">مرجوعی‌های من</a><a href="/cancellations/"> درخواست‌های لغو ارسال</a>
    {error && <p role="alert">{error}</p>}{signedOut ? <a href="/login/">برای مشاهدهٔ سفارش‌ها وارد شوید</a> : loading ? <p>در حال بارگذاری...</p> : <>
      {!orders.length && <p>هنوز سفارشی ثبت نکرده‌اید.</p>}<ul className="admin-list">{orders.map((order) => <li className="admin-record" key={order.id}><div><strong>سفارش #{order.id}</strong><p>{labels[order.status] ?? order.status} · {order.grand_total_toman.toLocaleString("fa-IR")} تومان</p><p>{new Date(order.created_at).toLocaleString("fa-IR")}</p></div><button disabled={busy} onClick={() => void detail(order.id)}>جزئیات</button></li>)}</ul>
      {selected && <section className="admin-card"><h2>سفارش #{selected.id}</h2><PaymentRecovery key={selected.id} orderId={selected.id} allowStart={selected.status === "pending_payment"} onUpdate={() => { void detail(selected.id); void load(); }} /><p>مالیات ثبت‌شدهٔ سفارش: {selected.tax_total_toman.toLocaleString("fa-IR")} تومان</p><a href={`/api/v1/commerce/orders/${selected.id}/invoice/`}>دریافت صورت سفارش</a><p>{labels[selected.status] ?? selected.status}</p><p>{selected.address.full_name} · {selected.address.province}، {selected.address.city}، {selected.address.street}</p>{selected.deliveries.map((delivery) => <section key={delivery.id}><h3>{delivery.seller}</h3><p>{delivery.shipping_method_label}{delivery.delivery_window_start && delivery.delivery_window_end && ` · تحویل انتخابی: ${new Date(delivery.delivery_window_start).toLocaleString("fa-IR")} تا ${new Date(delivery.delivery_window_end).toLocaleString("fa-IR")}`}</p><p>{labels[delivery.status] ?? delivery.status}{delivery.tracking_code && ` · کد پیگیری: ${delivery.tracking_code}`}</p>{selected.status === "paid" && ["awaiting_fulfillment", "packing"].includes(delivery.status) && <CancellationRequest deliveryId={delivery.id} status={delivery.cancellation_status} reload={() => void detail(selected.id)} />}{selected.status === "paid" && delivery.status !== "cancelled" && <DisputeRequest deliveryId={delivery.id} status={delivery.dispute_status} />}{selected.status === "paid" && delivery.status === "delivered" && <SellerRatingForm deliveryId={delivery.id} />}<ul>{delivery.lines.map((line) => <li key={line.id}>{line.product_title} × {line.quantity} · {line.line_total_toman.toLocaleString("fa-IR")} تومان · تخفیف: {line.discount_toman.toLocaleString("fa-IR")} · مالیات: {line.tax_toman.toLocaleString("fa-IR")} تومان{line.tax_label && ` (${line.tax_label})`}{delivery.status === "delivered" && <ReturnRequest deliveryId={delivery.id} lineId={line.id} maximum={line.quantity} />}</li>)}</ul></section>)}{selected.status === "pending_payment" && <button disabled={busy} onClick={() => void cancel(selected.id)}>لغو سفارش پرداخت‌نشده</button>}</section>}
    </>}
  </main>;
}
