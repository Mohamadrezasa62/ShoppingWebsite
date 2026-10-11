"use client";
import { FormEvent, useCallback, useEffect, useRef, useState } from "react";
import { apiRequest, csrfToken } from "@/lib/api";
type Job = { id: number; mode: "create" | "update"; status: string; row_count: number; attempt: number; event_status: string; error: { code?: string; row?: number }; product_ids: number[] };
const errors: Record<string, string> = { authorization_revoked: "دسترسی ثبت‌کننده تغییر کرده است", invalid_catalog_reference: "دسته یا برند در دسترس نیست", catalog_conflict: "نشانی یا SKU با دادهٔ کاتالوگ تعارض دارد", catalog_revision_conflict: "محصول پس از خروجی تغییر کرده یا حذف شده است" };

export function CatalogImports() {
  const [mode, setMode] = useState<"create" | "update">("create");
  const [exportAfter, setExportAfter] = useState("0"); const [exportDone, setExportDone] = useState(false);
  const [rows, setRows] = useState<Job[]>([]); const [notice, setNotice] = useState(""); const [busy, setBusy] = useState(false); const requestKey = useRef<string | null>(null);
  const load = useCallback(async () => { try { const response = await fetch("/api/v1/operations/catalog-imports/"); if (!response.ok) throw new Error(); setRows((await response.json()).imports); } catch { setNotice("گزارش ورودی‌ها دریافت نشد."); } }, []);
  useEffect(() => { void load(); }, [load]);
  async function upload(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); const form = event.currentTarget; setBusy(true); setNotice("");
    try {
      const csrf = await fetch("/api/v1/auth/csrf/"); if (!csrf.ok) throw new Error();
      const data = new FormData(form); requestKey.current ??= crypto.randomUUID(); data.set("idempotency_key", requestKey.current); data.set("mode", mode);
      const response = await fetch("/api/v1/operations/catalog-imports/", { method: "POST", headers: { "X-CSRFToken": csrfToken() ?? "" }, credentials: "same-origin", body: data });
      if (!response.ok) throw new Error(); form.reset(); requestKey.current = null; setNotice("فایل ثبت شد؛ وضعیت پردازش را به‌روزرسانی کنید."); await load();
    } catch { setNotice("ثبت انجام نشد؛ قالب، اندازه و داده‌های فایل را بررسی کنید. اگر ارتباط قطع شد، همان فایل را دوباره ارسال کنید."); } finally { setBusy(false); }
  }
  async function retry(event: FormEvent<HTMLFormElement>, id: number) {
    event.preventDefault(); const data = new FormData(event.currentTarget); setBusy(true);
    try { const response = await apiRequest("POST", `/api/v1/operations/catalog-imports/${id}/retry/`, { reason: data.get("reason") }); if (!response.ok) throw new Error(); await load(); }
    catch { setNotice("تلاش مجدد ثبت نشد؛ دادهٔ مرجع یا دسترسی ثبت‌کننده را بررسی کنید."); } finally { setBusy(false); }
  }
  async function exportBatch() {
    setBusy(true); setNotice("");
    try {
      const response = await fetch(`/api/v1/operations/catalog-imports/${mode === "update" ? "update-export" : "export"}/?after_id=${exportAfter}`);
      if (!response.ok) throw new Error();
      const url = URL.createObjectURL(await response.blob()); const link = document.createElement("a"); link.href = url; link.download = `catalog-after-${exportAfter}.csv`; document.body.appendChild(link); link.click(); link.remove(); setTimeout(() => URL.revokeObjectURL(url), 1000);
      const next = response.headers.get(mode === "update" ? "X-Next-Product-ID" : "X-Next-Variant-ID") ?? "0"; setExportAfter(next); setExportDone(next === "0");
    } catch { setNotice("دریافت خروجی انجام نشد."); } finally { setBusy(false); }
  }
  return <section className="admin-card"><h2>ورود و ویرایش گروهی کاتالوگ</h2><label>نوع عملیات<select value={mode} disabled={busy} onChange={(event) => { setMode(event.target.value as "create" | "update"); setExportAfter("0"); setExportDone(false); requestKey.current = null; }}><option value="create">ایجاد پیش‌نویس جدید</option><option value="update">ویرایش محتوای محصول موجود</option></select></label><p>CSV با encoding UTF-8، حداکثر ۱ مگابایت و ۲۵۰ ردیف. ستون‌ها و ترتیب را از قالب حفظ کنید؛ دسته و برند باید موجود و فعال باشند. همهٔ محصولات به صورت پیش‌نویس ایجاد می‌شوند. نشانی یا SKU موجود و ردیف نامعتبر کل فایل را برمی‌گرداند؛ حالت ایجاد، محصولات موجود را ویرایش نمی‌کند. در حالت ویرایش، خروجی مخصوص ویرایش را دریافت و تنها عنوان، توضیح و مشخصات را تغییر دهید؛ شناسه و revision باید حفظ شوند. تعارض نسخهٔ یک ردیف کل فایل را برمی‌گرداند. قیمت، موجودی، مدل، نشانی محصول و وضعیت انتشار تغییر نمی‌کنند.</p><p>خروجی کاتالوگ در بخش‌های ۲۵۰ مدلی دریافت می‌شود؛ متن مشکوک به فرمول برای بازکردن امن در صفحه‌گسترده خنثی می‌شود. خروجی حالت ایجاد برای ویرایش قابل استفاده نیست؛ خروجی حالت ویرایش ستون‌های متفاوت دارد. پیشوند خنثی‌کنندهٔ فرمول را پیش از ورود دوباره بررسی کنید. هیچ‌یک بکاپ کامل نیستند.</p><button disabled={busy || exportDone} onClick={() => void exportBatch()}>{exportDone ? "خروجی به پایان رسید" : "دریافت بخش بعدی CSV کاتالوگ"}</button><button disabled={busy} onClick={() => { setExportAfter("0"); setExportDone(false); }}>شروع دوبارهٔ خروجی</button>{mode === "create" && <a href="/api/v1/operations/catalog-imports/template/">دریافت قالب ایجاد CSV</a>}
    <form className="admin-inline-form" onSubmit={upload}><label>فایل<input name="file" type="file" accept=".csv,text/csv" required disabled={busy} onChange={() => { requestKey.current = null; }} /></label><label>دلیل<input name="reason" required minLength={3} maxLength={500} disabled={busy} /></label><button disabled={busy}>ثبت برای پردازش</button></form>{notice && <p role="status">{notice}</p>}
    <button disabled={busy} onClick={() => void load()}>به‌روزرسانی وضعیت پردازش</button>
    <ul className="admin-list">{rows.map((row) => <li className="admin-record" key={row.id}><div><h3>ورودی #{row.id}</h3><p>{row.mode === "update" ? "ویرایش محتوا" : "ایجاد پیش‌نویس"} · {row.status} · {row.row_count} ردیف · تلاش {row.attempt} · صف {row.event_status}</p>{row.error.code && <p>{errors[row.error.code] ?? "پردازش ناموفق"}{row.error.row && ` · ردیف ${row.error.row}`}</p>}{row.status === "succeeded" && <p>{row.mode === "update" ? "شناسهٔ محصولات ویرایش‌شده:" : "شناسهٔ پیش‌نویس‌های ایجادشده:"} {row.product_ids.join("، ")}</p>}</div>{(row.status === "failed" || row.event_status === "dead") && row.attempt < 5 && <form className="admin-inline-form" onSubmit={(event) => void retry(event, row.id)}><label>دلیل تلاش مجدد<input name="reason" required minLength={3} maxLength={500} /></label><button disabled={busy}>پردازش دوبارهٔ همین داده</button></form>}</li>)}</ul>
  </section>;
}
