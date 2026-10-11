"use client";
import { FormEvent, useCallback, useEffect, useRef, useState } from "react";
import { apiRequest } from "@/lib/api";

type Note = { id: number; actor_id: number; body: string; created_at: string };
export function PaymentInvestigation({ attemptId }: { attemptId: number }) {
  const [open, setOpen] = useState(false); const [rows, setRows] = useState<Note[]>([]);
  const [body, setBody] = useState(""); const [notice, setNotice] = useState("");
  const [busy, setBusy] = useState(false); const [loading, setLoading] = useState(false);
  const [cursors, setCursors] = useState<(number | null)[]>([null]); const [next, setNext] = useState<number | null>(null);
  const generation = useRef(0); const retry = useRef<{ body: string; key: string } | null>(null);
  const before = cursors[cursors.length - 1];
  const load = useCallback(async () => {
    if (!open) return; const current = ++generation.current; setLoading(true);
    try {
      const response = await fetch(`/api/v1/payments/finance/${attemptId}/notes/${before ? `?before=${before}` : ""}`, { cache: "no-store" });
      if (!response.ok) throw new Error(); const result = await response.json();
      if (current === generation.current) { setRows(result.notes); setNext(result.next_before); }
    } catch { if (current === generation.current) { setRows([]); setNext(null); setNotice("سوابق پیگیری دریافت نشد."); } }
    finally { if (current === generation.current) setLoading(false); }
  }, [attemptId, before, open]);
  useEffect(() => { void load(); return () => { generation.current++; }; }, [load]);
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); setBusy(true); setNotice(""); const reason = body.trim();
    if (!retry.current || retry.current.body !== reason) retry.current = { body: reason, key: crypto.randomUUID() };
    try {
      const response = await apiRequest("POST", `/api/v1/payments/finance/${attemptId}/notes/append/`, { reason, request_key: retry.current.key });
      if (!response.ok) throw new Error();
      retry.current = null; setBody(""); setNotice("پیگیری ثبت شد؛ وضعیت پرداخت و سفارش تغییری نکرد.");
      if (before) setCursors([null]); else await load();
    } catch { setNotice("ثبت پیگیری تأیید نشد؛ برای همان متن دوباره تلاش کنید."); }
    finally { setBusy(false); }
  }
  return <section><button disabled={busy || loading} aria-expanded={open} onClick={() => setOpen(!open)}>سوابق پیگیری مالی</button>
    {open && <><p>یادداشت داخلی پیگیری است؛ اطلاعات کارت، رمز، کلید درگاه یا مشخصات شخصی را وارد نکنید.</p>
      <form onSubmit={submit}><label>شرح پیگیری<textarea required minLength={3} maxLength={500} disabled={busy} value={body} onChange={(event) => setBody(event.target.value)} /></label><button disabled={busy || loading || body.trim().length < 3}>ثبت پیگیری</button></form>
      {notice && <p role="status">{notice}</p>}
      <button disabled={busy || loading} onClick={() => void load()}>تازه‌سازی سوابق</button>
      {loading ? <p>در حال دریافت…</p> : <><ul>{rows.map((row) => <li key={row.id}><p>{row.body}</p><small>کارمند #{row.actor_id} · {new Date(row.created_at).toLocaleString("fa-IR")}</small></li>)}</ul>{!rows.length && <p>پیگیری ثبت نشده است.</p>}</>}
      <button disabled={busy || loading || cursors.length === 1} onClick={() => setCursors((values) => values.slice(0, -1))}>جدیدتر</button><button disabled={busy || loading || !next} onClick={() => setCursors((values) => [...values, next])}>قدیمی‌تر</button>
    </>}
  </section>;
}
