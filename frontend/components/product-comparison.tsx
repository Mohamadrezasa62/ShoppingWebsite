"use client";
import { FormEvent, useEffect, useState } from "react";
type Card = { id: number; title: string; slug: string; starting_price_toman: number };
type Compared = Card & { brand: string | null; category: string; specifications: Record<string, string>; image: { url: string; alt: string } | null };
export function ProductComparison() {
  const [ids, setIds] = useState<number[]>([]); const [ready, setReady] = useState(false); const [query, setQuery] = useState(""); const [results, setResults] = useState<Card[]>([]); const [products, setProducts] = useState<Compared[]>([]); const [keys, setKeys] = useState<string[]>([]); const [notice, setNotice] = useState(""); const [busy, setBusy] = useState(false);
  useEffect(() => {
    const values = (new URLSearchParams(window.location.search).get("ids") ?? "").split(",").map(Number).filter((id) => Number.isSafeInteger(id) && id > 0);
    setIds([...new Set(values)].slice(0, 4)); setReady(true);
  }, []);
  useEffect(() => {
    if (!ready) return;
    const url = new URL(window.location.href); if (ids.length) url.searchParams.set("ids", ids.join(",")); else url.searchParams.delete("ids"); window.history.replaceState(null, "", url);
    setProducts([]); setKeys([]); if (ids.length < 2) return;
    let current = true;
    fetch(`/api/v1/catalog/compare/?ids=${ids.join(",")}`).then(async (response) => { if (!response.ok) throw new Error(); const data = await response.json(); if (current) { setProducts(data.products); setKeys(data.specification_keys); setNotice(""); } }).catch(() => { if (current) setNotice("یکی از محصولات اکنون قابل خرید نیست؛ انتخاب را تغییر دهید."); });
    return () => { current = false; };
  }, [ids, ready]);
  async function search(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); setBusy(true);
    try { const response = await fetch(`/api/v1/catalog/products/?q=${encodeURIComponent(query)}`); if (!response.ok) throw new Error(); setResults((await response.json()).products); }
    catch { setNotice("جست‌وجو انجام نشد."); } finally { setBusy(false); }
  }
  return <section><h1>مقایسهٔ محصولات</h1><p>دو تا چهار محصول انتخاب کنید. قیمت‌ها از پیشنهادهای موجود هستند؛ انتخاب مدل و مبلغ نهایی را در صفحهٔ محصول و سبد بررسی کنید.</p><form className="admin-inline-form" onSubmit={search}><label>جست‌وجوی محصول<input value={query} onChange={(event) => setQuery(event.target.value)} maxLength={120} /></label><button disabled={busy}>جست‌وجو</button></form>{notice && <p role="status">{notice}</p>}<ul className="admin-list">{results.map((row) => <li key={row.id}>{row.title} · {row.starting_price_toman.toLocaleString("fa-IR")} تومان <button disabled={ids.includes(row.id) || ids.length >= 4} onClick={() => setIds((current) => [...current, row.id])}>افزودن به مقایسه</button></li>)}</ul><p>انتخاب‌شده: {ids.length} از ۴</p>{ids.map((id) => <button key={id} onClick={() => setIds((current) => current.filter((value) => value !== id))}>حذف {products.find((row) => row.id === id)?.title ?? `محصول #${id}`}</button>)}{products.length > 0 && <div style={{ overflowX: "auto" }}><table className="comparison-table"><caption>مشخصات محصولات انتخاب‌شده</caption><thead><tr><th scope="col">ویژگی</th>{products.map((row) => <th scope="col" key={row.id}><a href={`/products/${encodeURIComponent(row.slug)}/`}>{row.title}</a>{row.image && <img src={row.image.url} alt={row.image.alt} width={120} loading="lazy" />}</th>)}</tr></thead><tbody><tr><th scope="row">قیمت از</th>{products.map((row) => <td key={row.id}>{row.starting_price_toman.toLocaleString("fa-IR")} تومان</td>)}</tr><tr><th scope="row">برند</th>{products.map((row) => <td key={row.id}>{row.brand ?? "—"}</td>)}</tr><tr><th scope="row">دسته</th>{products.map((row) => <td key={row.id}>{row.category}</td>)}</tr>{keys.map((key) => <tr key={key}><th scope="row">{key}</th>{products.map((row) => <td key={row.id}>{row.specifications[key] ?? "—"}</td>)}</tr>)}</tbody></table></div>}</section>;
}
