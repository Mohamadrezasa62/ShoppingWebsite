"use client";
import { useEffect, useState } from "react";
import { apiRequest } from "@/lib/api";
type Notice = { id: number; title: string; body: string; link: string; read: boolean };
export default function NotificationsPage() {
  const [items, setItems] = useState<Notice[]>([]); const [error, setError] = useState("");
  useEffect(() => { fetch("/api/v1/operations/notifications/").then(async (response) => { if (!response.ok) throw new Error(); setItems((await response.json()).notifications); }).catch(() => setError("اعلان‌ها دریافت نشدند؛ وارد حساب شوید.")); }, []);
  async function read(id: number) {
    try { const response = await apiRequest("POST", `/api/v1/operations/notifications/${id}/read/`); if (!response.ok) throw new Error(); setItems((current) => current.map((item) => item.id === id ? { ...item, read: true } : item)); }
    catch { setError("ثبت انجام نشد."); }
  }
  return <main className="catalog-main"><a href="/account/">حساب من</a><h1>اعلان‌ها</h1>{error && <p role="alert">{error}</p>}<ul className="admin-list">{items.map((item) => <li key={item.id}><strong>{item.title}</strong><p>{item.body}</p><a href={item.link.startsWith("/") && !item.link.startsWith("//") ? item.link : "/account/"}>مشاهده</a>{!item.read && <button onClick={() => void read(item.id)}>خوانده شد</button>}</li>)}</ul></main>;
}
