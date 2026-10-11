"use client";

import { FormEvent, useCallback, useEffect, useState } from "react";
import { apiRequest } from "@/lib/api";

type Delivery = { shipping_method_label?: string; delivery_window_start?: string | null; delivery_window_end?: string | null; id: number; order_id?: number; seller?: string; status: string; cancellation_status?: string|null; tracking_code: string; lines: { id: number; product_title: string; quantity: number }[] };
type Order = { id: number; status: string; grand_total_toman: number };

function DeliveryRow({ delivery, endpoint, admin, reload }: { delivery: Delivery; endpoint: string; admin: boolean; reload: () => Promise<void> }) {
  const [notice, setNotice] = useState("");
  const [busy, setBusy] = useState(false);
  const held = ["requested", "approved"].includes(delivery.cancellation_status ?? "");
  const next = held ? null : delivery.status === "awaiting_fulfillment" ? "packing" : delivery.status === "packing" ? "shipped" : admin && delivery.status === "shipped" ? "delivered" : null;
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); setBusy(true); setNotice("");
    const values = new FormData(event.currentTarget);
    try {
      const response = await apiRequest("POST", endpoint, { status: next, tracking_code: values.get("tracking") ?? "", ...(admin ? { reason: values.get("reason") } : {}) });
      if (!response.ok) throw new Error();
      await reload();
    } catch { setNotice("ثبت تغییر انجام نشد؛ وضعیت را دوباره بررسی کنید."); }
    finally { setBusy(false); }
  }
  return <li className="admin-record"><div><strong>ارسال #{delivery.id}{delivery.order_id && ` · سفارش #${delivery.order_id}`}</strong><p>{delivery.seller} · {delivery.status} · {delivery.shipping_method_label}</p>{delivery.delivery_window_start && delivery.delivery_window_end && <p>تحویل انتخابی: {new Date(delivery.delivery_window_start).toLocaleString("fa-IR")} تا {new Date(delivery.delivery_window_end).toLocaleString("fa-IR")}</p>}{held && <p>آماده‌سازی و ارسال تا بررسی درخواست لغو متوقف است.</p>}<ul>{delivery.lines.map((line) => <li key={line.id}>{line.product_title} × {line.quantity}</li>)}</ul>{delivery.tracking_code && <p>کد پیگیری: {delivery.tracking_code}</p>}</div>
    {next && <form className="admin-inline-form" onSubmit={submit}>{next === "shipped" && <label>کد پیگیری<input name="tracking" required maxLength={120} /></label>}{admin && <label>دلیل تغییر<input name="reason" required minLength={3} maxLength={500} /></label>}<button disabled={busy}>{next === "packing" ? "شروع بسته‌بندی" : next === "shipped" ? "ثبت ارسال" : "تأیید تحویل"}</button></form>}
    {notice && <p role="alert">{notice}</p>}</li>;
}

export function SellerFulfillment({ storeId }: { storeId: number }) {
  const [deliveries, setDeliveries] = useState<Delivery[]>([]);
  const [error, setError] = useState("");
  const load = useCallback(async () => {
    try {
      const response = await fetch(`/api/v1/seller/stores/${storeId}/deliveries/`);
      if (!response.ok) throw new Error();
      setDeliveries((await response.json()).deliveries);
    } catch { setError("سفارش‌های فروشگاه دریافت نشدند."); }
  }, [storeId]);
  useEffect(() => { void load(); }, [load]);
  return <section className="admin-card seller-section"><h2>سفارش‌های پرداخت‌شده</h2>{error && <p role="alert">{error}</p>}{!deliveries.length && <p>سفارشی برای آماده‌سازی نیست.</p>}<ul className="admin-list">{deliveries.map((delivery) => <DeliveryRow key={`${delivery.id}-${delivery.status}`} delivery={delivery} admin={false} endpoint={`/api/v1/seller/stores/${storeId}/deliveries/${delivery.id}/transition/`} reload={load} />)}</ul></section>;
}

export function AdminOrders() {
  const [orders, setOrders] = useState<Order[]>([]);
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [deliveries, setDeliveries] = useState<Delivery[]>([]);
  const [error, setError] = useState("");
  const [page, setPage] = useState(1);
  const [hasNext, setHasNext] = useState(false);
  const [canManage, setCanManage] = useState(false);
  useEffect(() => {
    fetch("/api/v1/auth/me/").then((response) => response.json()).then((profile) => setCanManage(profile.is_superuser || profile.staff_roles?.some((role: string) => ["marketplace_manager", "system_administrator"].includes(role)))).catch(() => setCanManage(false));
  }, []);
  useEffect(() => {
    fetch(`/api/v1/operations/orders/?page=${page}`).then(async (response) => {
      if (!response.ok) throw new Error();
      const data = await response.json(); setOrders(data.orders); setHasNext(data.has_next);
    }).catch(() => setError("سفارش‌ها دریافت نشدند."));
  }, [page]);
  const detail = useCallback(async () => {
    if (!selectedId) return;
    try {
      const response = await fetch(`/api/v1/operations/orders/${selectedId}/`);
      if (!response.ok) throw new Error();
      setDeliveries((await response.json()).order.deliveries);
    } catch { setError("جزئیات سفارش دریافت نشد."); }
  }, [selectedId]);
  useEffect(() => { setDeliveries([]); void detail(); }, [detail]);
  return <section className="admin-card"><h1>سفارش‌ها و ارسال</h1>{error && <p role="alert">{error}</p>}<ul className="admin-list">{orders.map((order) => <li className="admin-record" key={order.id}><div>سفارش #{order.id} · {order.status} · {order.grand_total_toman.toLocaleString("fa-IR")} تومان</div><button onClick={() => setSelectedId(order.id)}>جزئیات</button></li>)}</ul><div className="cart-actions"><button disabled={page === 1} onClick={() => setPage(page - 1)}>قبلی</button><span>{page}</span><button disabled={!hasNext} onClick={() => setPage(page + 1)}>بعدی</button></div>
    {selectedId && <><h2>ارسال‌های سفارش #{selectedId}</h2><ul className="admin-list">{deliveries.map((delivery) => canManage ? <DeliveryRow key={`${delivery.id}-${delivery.status}`} delivery={delivery} admin endpoint={`/api/v1/operations/deliveries/${delivery.id}/transition/`} reload={detail} /> : <li key={delivery.id}>{delivery.seller} · {delivery.status} · {delivery.tracking_code}</li>)}</ul></>}
  </section>;
}
