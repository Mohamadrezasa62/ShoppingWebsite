"use client";
import { FormEvent, useCallback, useEffect, useRef, useState } from "react";
import { apiRequest } from "@/lib/api";
type Page = { id: number; title: string; slug: string; body: string; kind: string; is_published: boolean; version: number; publish_after: string | null; publish_until: string | null };
type Revision = { version: number; reason: string; created_at: string; snapshot: Omit<Page, "id"> };
function localTime(value: string | null): string {
  if (!value) return "";
  const date = new Date(value);
  return new Date(date.getTime() - date.getTimezoneOffset() * 60000).toISOString().slice(0, 16);
}
function PageForm({page, changed}: {page?: Page; changed: () => Promise<void>}) {
  const [busy, setBusy] = useState(false); const [notice, setNotice] = useState("");
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); const form = event.currentTarget; const data = new FormData(form);
    setBusy(true); setNotice("");
    try {
      const after = String(data.get("publish_after") || ""), until = String(data.get("publish_until") || "");
      const payload = { title: data.get("title"), slug: data.get("slug"), body: data.get("body"), kind: data.get("kind"), is_published: data.get("published") === "on", reason: data.get("reason"), publish_after: after ? new Date(after).toISOString() : null, publish_until: until ? new Date(until).toISOString() : null, ...(page ? {version: page.version} : {}) };
      const response = await apiRequest(page ? "PATCH" : "POST", `/api/v1/operations/pages/${page ? `${page.id}/` : ""}`, payload);
      if (response.status === 409) { setNotice("نسخهٔ صفحه تغییر کرده است؛ متن فعلی را کپی و فهرست را تازه‌سازی کنید تا تغییر دیگران از بین نرود."); return; }
      if (!response.ok) throw new Error();
      if (!page) form.reset(); await changed(); setNotice("ذخیره شد.");
    } catch { setNotice("ذخیره نشد؛ نشانی یکتا و ترتیب زمان‌های انتشار را بررسی کنید."); } finally { setBusy(false); }
  }
  return <form className="admin-inline-form" onSubmit={submit}><label>عنوان<input name="title" required maxLength={200} defaultValue={page?.title} /></label><label>نشانی<input name="slug" required maxLength={200} defaultValue={page?.slug} /></label><label>نوع<select name="kind" defaultValue={page?.kind ?? "guide"}><option value="guide">راهنما</option><option value="policy">قوانین</option><option value="campaign">کمپین</option></select></label><label>متن ساده<textarea name="body" required maxLength={50000} defaultValue={page?.body} /></label><label><input name="published" type="checkbox" defaultChecked={page?.is_published ?? false} />انتشار در بازهٔ مشخص‌شده</label><label>شروع انتشار (زمان دستگاه)<input name="publish_after" type="datetime-local" defaultValue={localTime(page?.publish_after ?? null)} /></label><label>پایان انتشار (زمان دستگاه)<input name="publish_until" type="datetime-local" defaultValue={localTime(page?.publish_until ?? null)} /></label><label>دلیل<input name="reason" required minLength={3} maxLength={500} /></label><button disabled={busy}>{page ? "ذخیرهٔ نسخهٔ تازه" : "ثبت صفحه"}</button>{notice && <p role="status">{notice}</p>}</form>;
}
function RevisionHistory({page, changed}: {page: Page; changed: () => Promise<void>}) {
  const [rows, setRows] = useState<Revision[]>([]); const [before, setBefore] = useState<number | null>(null);
  const [notice, setNotice] = useState(""); const [busy, setBusy] = useState(false);
  async function load(cursor?: number) {
    setBusy(true); setNotice("");
    try {
      const response = await fetch(`/api/v1/operations/pages/${page.id}/revisions/${cursor ? `?before=${cursor}` : ""}`);
      if (!response.ok) throw new Error(); const data = await response.json(); setRows(previous => cursor ? [...previous, ...data.revisions] : data.revisions); setBefore(data.next_before);
    } catch { setNotice("تاریخچه دریافت نشد."); } finally { setBusy(false); }
  }
  async function restore(event: FormEvent<HTMLFormElement>, revision: Revision) {
    event.preventDefault(); setBusy(true); setNotice("");
    const data = new FormData(event.currentTarget);
    try {
      const response = await apiRequest("POST", `/api/v1/operations/pages/${page.id}/restore/`, {version: page.version, restore_version: revision.version, reason: data.get("reason")});
      if (response.status === 409) { setNotice("نسخهٔ جاری تغییر کرده است؛ فهرست را تازه‌سازی کنید."); return; }
      if (!response.ok) throw new Error(); await changed();
    } catch { setNotice("بازگردانی انجام نشد؛ ممکن است نشانی نسخهٔ قبلی دیگر قابل استفاده نباشد."); } finally { setBusy(false); }
  }
  return <details><summary>تاریخچه و بازگردانی</summary><p>بازگردانی یک پیش‌نویس تازه می‌سازد؛ انتشار و زمان‌بندی قبلی دوباره فعال نمی‌شوند.</p><button type="button" disabled={busy} onClick={() => void load()}>دریافت تاریخچه</button>{rows.map(row => <details key={row.version}><summary>نسخهٔ {row.version} · {new Date(row.created_at).toLocaleString("fa-IR")}</summary><p>{row.reason}</p><h3>{row.snapshot.title}</h3><p style={{whiteSpace: "pre-wrap"}}>{row.snapshot.body}</p><form className="admin-inline-form" onSubmit={event => void restore(event, row)}><label>دلیل بازگردانی<input name="reason" required minLength={3} maxLength={500} /></label><button disabled={busy}>بازگردانی به پیش‌نویس</button></form></details>)}{before && <button type="button" disabled={busy} onClick={() => void load(before)}>نسخه‌های قدیمی‌تر</button>}{notice && <p role="status">{notice}</p>}</details>;
}
export function ContentWorkspace() {
  const [pages, setPages] = useState<Page[]>([]); const [notice, setNotice] = useState("");
  const [number, setNumber] = useState(1); const [hasNext, setHasNext] = useState(false); const [loading, setLoading] = useState(false);
  const latestLoad = useRef(0); const currentNumber = useRef(1);
  const load = useCallback(async () => {
    if (number !== currentNumber.current) return;
    const request = ++latestLoad.current; setLoading(true);
    try {
      const response = await fetch(`/api/v1/operations/pages/?page=${number}`);
      if (!response.ok) throw new Error(); const data = await response.json();
      if (request === latestLoad.current) { setPages(data.pages); setHasNext(data.has_next); setNotice(""); }
    } catch { if (request === latestLoad.current) setNotice("محتوا دریافت نشد."); }
    finally { if (request === latestLoad.current) setLoading(false); }
  }, [number]);
  useEffect(() => { void load(); }, [load]);
  return <section className="admin-card"><h1>محتوا و راهنماها</h1><p>تاریخ‌ها به زمان دستگاه وارد می‌شوند. شروع و پایان خالی یعنی بدون محدودیت زمانی. ویرایش صفحهٔ فعال، نسخهٔ عمومی را تغییر می‌دهد؛ برای کار روی پیش‌نویس، انتشار را خاموش کنید. تغییر نشانی، نشانی قبلی را خودکار هدایت نمی‌کند.</p>{notice && <p role="status">{notice}</p>}<button type="button" disabled={loading} onClick={() => void load()}>تازه‌سازی فهرست</button><p>صفحهٔ {number}</p><button type="button" disabled={loading || number === 1} onClick={() => { latestLoad.current++; setPages([]); currentNumber.current = number-1; setNumber(number-1); }}>صفحهٔ قبل</button><button type="button" disabled={loading || !hasNext} onClick={() => { latestLoad.current++; setPages([]); currentNumber.current = number+1; setNumber(number+1); }}>صفحهٔ بعد</button><h2>صفحهٔ تازه</h2><PageForm changed={load} /><ul className="admin-list">{pages.map(page => <li key={page.id}><h2>{page.title} · نسخهٔ {page.version}</h2><p>{page.is_published ? "انتشار فعال طبق زمان‌بندی" : "پیش‌نویس"}</p><a href={`/content/${encodeURIComponent(page.slug)}/`}>مشاهدهٔ صفحهٔ عمومی</a><details><summary>پیش‌نمایش خصوصی متن فعلی</summary><article><h3>{page.title}</h3><p style={{whiteSpace: "pre-wrap"}}>{page.body}</p></article></details><details><summary>ویرایش متن و زمان‌بندی</summary><PageForm key={`${page.id}:${page.version}`} page={page} changed={load} /></details><RevisionHistory key={`${page.id}:${page.version}`} page={page} changed={load} /></li>)}</ul></section>;
}
