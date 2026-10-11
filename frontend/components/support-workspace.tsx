"use client";
import { FormEvent, useCallback, useEffect, useRef, useState } from "react";
import { apiRequest } from "@/lib/api";
type Ticket = { id: number; subject: string; status: string; order_id: number | null; assigned_to?: number | null; priority?: string; is_escalated?: boolean; has_older_messages: boolean; before_message: number | null; messages: { id: number; body: string; from_support: boolean; is_internal: boolean }[] };
export function SupportWorkspace({ admin = false, canReviewEscalation = false }: { admin?: boolean; canReviewEscalation?: boolean }) {
  const [tickets, setTickets] = useState<Ticket[]>([]); const [notice, setNotice] = useState(""); const [busy, setBusy] = useState(false);
  const [page, setPage] = useState(1); const [hasNext, setHasNext] = useState(false);
  const [status, setStatus] = useState(""); const [assigned, setAssigned] = useState("");
  const [loading, setLoading] = useState(false); const generation = useRef(0);
  const attempts = useRef(new Map<string, { payload: string; key: string }>());
  async function submit(scope: string, path: string, payload: Record<string, unknown>) {
    const serialized = JSON.stringify(payload);
    let attempt = attempts.current.get(scope);
    if (!attempt || attempt.payload !== serialized) {
      attempt = { payload: serialized, key: crypto.randomUUID() };
      attempts.current.set(scope, attempt);
    }
    const response = await apiRequest("POST", path, { ...payload, request_key: attempt.key });
    if (response.ok) attempts.current.delete(scope);
    return response;
  }
  const [assignees, setAssignees] = useState<{ id: number; name: string }[]>([]);
  useEffect(() => { if (admin) fetch("/api/v1/operations/support-assignees/").then(async (response) => { if (!response.ok) throw new Error(); setAssignees((await response.json()).assignees); }).catch(() => setNotice("فهرست مسئولان دریافت نشد.")); }, [admin]);
  const base = `/api/v1/operations/${admin ? "tickets" : "my-tickets"}/`;
  const load = useCallback(async () => {
    const current = ++generation.current;
    setLoading(true);
    try {
      const query = new URLSearchParams({ page: String(page) });
      if (status) query.set("status", status);
      if (admin && assigned) query.set("assigned", assigned);
      const response = await fetch(`${base}?${query}`, { cache: "no-store" });
      if (!response.ok) throw new Error();
      const result = await response.json();
      if (current === generation.current) { setTickets(result.tickets); setHasNext(result.has_next); }
    } catch { if (current === generation.current) { setTickets([]); setHasNext(false); setNotice("درخواست‌ها دریافت نشدند؛ ابتدا وارد حساب شوید."); } }
    finally { if (current === generation.current) setLoading(false); }
  }, [base, page, status, admin, assigned]);
  useEffect(() => { void load(); return () => { generation.current++; }; }, [load]);
  async function older(ticket: Ticket) {
    if (!ticket.before_message) return;
    const current = generation.current;
    setBusy(true);
    try {
      const response = await fetch(`${base}${ticket.id}/?before=${ticket.before_message}`, { cache: "no-store" });
      if (!response.ok) throw new Error();
      const previous: Ticket = (await response.json()).ticket;
      if (current === generation.current) setTickets((rows) => rows.map((row) => row.id === ticket.id ? {
        ...row, has_older_messages: previous.has_older_messages, before_message: previous.before_message,
        messages: [...previous.messages.filter((message) => !row.messages.some((existing) => existing.id === message.id)), ...row.messages],
      } : row));
    } catch { if (current === generation.current) setNotice("پیام‌های قبلی دریافت نشدند؛ دوباره تلاش کنید."); }
    finally { setBusy(false); }
  }
  async function create(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); setBusy(true); const form = event.currentTarget; const data = new FormData(form);
    try { const response = await submit("create", base, { subject: data.get("subject"), body: data.get("body"), order_id: data.get("order") ? Number(data.get("order")) : null }); if (!response.ok) throw new Error(); form.reset(); await load(); }
    catch { setNotice("درخواست ثبت نشد؛ اطلاعات سفارش را بررسی کنید."); } finally { setBusy(false); }
  }
  async function reply(event: FormEvent<HTMLFormElement>, id: number) {
    event.preventDefault(); setBusy(true); const form = event.currentTarget; const data = new FormData(form);
    try { const response = await submit(`reply:${id}`, `${base}${id}/reply/`, { body: data.get("body"), ...(admin ? { status: data.get("status"), reason: data.get("reason"), is_internal: data.get("internal") === "on" } : {}) }); if (!response.ok) throw new Error(); form.reset(); await load(); }
    catch { setNotice("پاسخ ثبت نشد؛ وضعیت درخواست را بررسی کنید."); } finally { setBusy(false); }
  }
  async function route(event: FormEvent<HTMLFormElement>, id: number) {
    event.preventDefault(); setBusy(true); const values = new FormData(event.currentTarget);
    try { const response = await submit(`route:${id}`, `${base}${id}/route/`, { assigned_to: values.get("assignee") ? Number(values.get("assignee")) : null, priority: values.get("priority"), is_escalated: values.get("escalated") === "on", reason: values.get("reason") }); if (!response.ok) throw new Error(); await load(); setNotice("مسیر و اولویت ثبت شدند."); }
    catch { setNotice("ارجاع ثبت نشد؛ پروندهٔ ارجاع‌شده به مسئول مدیریتی نیاز دارد و فقط مدیر می‌تواند آن را از ارجاع خارج کند."); } finally { setBusy(false); }
  }
  return <section className="admin-card"><h1>پشتیبانی</h1><div className="admin-inline-form"><label>وضعیت درخواست<select value={status} disabled={busy || loading} onChange={(event) => { setStatus(event.target.value); setPage(1); }}><option value="">همه</option>{["open", "awaiting_customer", "resolved", "closed"].map((value) => <option key={value}>{value}</option>)}</select></label>{admin && <label>مسئول<select value={assigned} disabled={busy || loading} onChange={(event) => { setAssigned(event.target.value); setPage(1); }}><option value="">همه</option><option value="mine">ارجاع به من</option><option value="unassigned">بدون مسئول</option></select></label>}<button disabled={busy || loading} onClick={() => void load()}>تازه‌سازی</button><button disabled={busy || loading || page === 1} onClick={() => setPage(page - 1)}>صفحهٔ قبل</button><span>صفحهٔ {page}</span><button disabled={busy || loading || !hasNext} onClick={() => setPage(page + 1)}>صفحهٔ بعد</button></div>{loading && <p role="status">در حال دریافت درخواست‌ها…</p>}{notice && <p role="status">{notice}</p>}{!admin && <form className="admin-inline-form" onSubmit={create}><label>موضوع<input name="subject" required minLength={3} maxLength={200} /></label><label>شمارهٔ سفارش (اختیاری)<input name="order" type="number" min={1} /></label><label>پیام<textarea name="body" required maxLength={5000} /></label><button disabled={busy || loading}>درخواست جدید</button></form>}
    <ul className="admin-list">{!loading && tickets.map((ticket) => <li key={ticket.id}><h2>#{ticket.id} · {ticket.subject}</h2><p>{ticket.status}{ticket.order_id && ` · سفارش #${ticket.order_id}`}</p>{admin && <p>{ticket.is_escalated ? "ارجاع مدیریتی" : "بررسی عادی"} · {ticket.priority === "urgent" ? "فوری" : ticket.priority === "high" ? "اولویت بالا" : "اولویت عادی"}</p>}{admin && ticket.status !== "closed" && <form key={`${ticket.id}-${ticket.assigned_to}-${ticket.priority}-${ticket.is_escalated}`} className="admin-inline-form" onSubmit={(event) => void route(event, ticket.id)}><label>مسئول<select name="assignee" defaultValue={ticket.assigned_to ?? ""}><option value="">بدون مسئول</option>{assignees.map((person) => <option key={person.id} value={person.id}>{person.name}</option>)}</select></label><label>اولویت<select name="priority" defaultValue={ticket.priority ?? "normal"}><option value="normal">عادی</option><option value="high">بالا</option><option value="urgent">فوری</option></select></label><label><input name="escalated" type="checkbox" defaultChecked={ticket.is_escalated} disabled={ticket.is_escalated && !canReviewEscalation} /> ارجاع مدیریتی</label>{ticket.is_escalated && !canReviewEscalation && <input type="hidden" name="escalated" value="on" />}<label>دلیل<input name="reason" required minLength={3} maxLength={500} /></label><button disabled={busy || loading}>ذخیرهٔ ارجاع</button></form>}{ticket.has_older_messages && <button disabled={busy || loading} onClick={() => void older(ticket)}>نمایش پیام‌های قبلی</button>}{ticket.messages.map((message) => <p key={message.id}><strong>{message.from_support ? "پشتیبانی" : "کاربر"}{message.is_internal && " (یادداشت داخلی)"}: </strong>{message.body}</p>)}{(admin || ticket.status !== "closed") && <form className="admin-inline-form" onSubmit={(event) => void reply(event, ticket.id)}><label>پاسخ<textarea name="body" required maxLength={5000} /></label>{admin && <><label>وضعیت<select name="status" defaultValue="awaiting_customer">{["open", "awaiting_customer", "resolved", "closed"].map((status) => <option key={status}>{status}</option>)}</select></label><label><input name="internal" type="checkbox" /> یادداشت داخلی</label><label>دلیل<input name="reason" required minLength={3} maxLength={500} /></label></>}<button disabled={busy || loading}>ارسال پاسخ</button></form>}</li>)}</ul>
  </section>;
}
