"use client";
import { useCallback, useEffect, useState } from "react";
import { apiRequest } from "@/lib/api";
type Alert = { id: number; product: string; slug: string; kind: string; target_price_toman: number | null; active: boolean };
export default function AlertsPage() {
  const [rows, setRows] = useState<Alert[]>([]), [notice, setNotice] = useState(""), [busy, setBusy] = useState(false);
  const load = useCallback(async () => { try { const response = await fetch("/api/v1/catalog/alerts/"); if (!response.ok) { setNotice(response.status === 401 ? "ابتدا وارد حساب شوید." : "اعلان‌ها دریافت نشدند."); return; } setRows((await response.json()).alerts); } catch { setNotice("ارتباط برقرار نشد."); } }, []);
  useEffect(() => { void load(); }, [load]);
  async function remove(id: number) { setBusy(true); try { const response = await apiRequest("DELETE", `/api/v1/catalog/alerts/${id}/`); if (!response.ok) throw new Error(); await load(); } catch { setNotice("حذف انجام نشد."); } finally { setBusy(false); } }
  return <main className="admin-shell"><section className="admin-card"><h1>اعلان‌های محصول من</h1><a href="/account/">حساب من</a>{notice && <p role="status">{notice}</p>}<ul className="admin-list">{rows.map(row => <li key={row.id}><a href={`/products/${row.slug}/`}>{row.product}</a><p>{row.kind === "price_drop" ? `قیمت حداکثر ${row.target_price_toman?.toLocaleString("fa-IR")} تومان` : "موجود شدن"} · {row.active ? "در انتظار" : "اعلان ثبت شده"}</p><button disabled={busy} onClick={() => void remove(row.id)}>حذف اشتراک</button></li>)}</ul>{!rows.length && <p>اشتراکی ثبت نشده است.</p>}</section></main>;
}
