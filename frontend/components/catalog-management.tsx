"use client";

import { FormEvent, useCallback, useEffect, useState } from "react";
import { apiRequest } from "@/lib/api";

type Product = { id: number; title: string; slug: string; status: string; category_id: number; brand_id: number | null; description: string; specifications: Record<string, string> };
type Brand = { id: number; name: string; is_active: boolean };
type Category = { id: number; name: string };

export function CatalogManagement() {
  const [brands, setBrands] = useState<Brand[]>([]);
  const [products, setProducts] = useState<Product[]>([]);
  const [categories, setCategories] = useState<Category[]>([]);
  const [page, setPage] = useState(1);
  const [hasNext, setHasNext] = useState(false);
  const [query, setQuery] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const load = useCallback(async () => {
    try {
      const response = await fetch(`/api/v1/operations/products/?page=${page}&q=${encodeURIComponent(query)}`);
      if (!response.ok) throw new Error();
      const data = await response.json();
      setProducts(data.products); setHasNext(data.has_next);
    } catch { setError("دریافت محصولات انجام نشد."); }
  }, [page, query]);
  useEffect(() => { void load(); }, [load]);
  useEffect(() => {
    fetch("/api/v1/operations/categories/").then(async (response) => {
      if (!response.ok) throw new Error();
      setCategories((await response.json()).categories);
    }).catch(() => setError("دسته‌بندی‌ها بارگذاری نشدند."));
  }, []);
  useEffect(() => { fetch("/api/v1/operations/brands/").then(async response => { if (!response.ok) throw new Error(); setBrands((await response.json()).brands); }).catch(() => setError("برندها بارگذاری نشدند.")); }, []);
  async function create(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); setBusy(true); setError("");
    const form = event.currentTarget;
    const values = new FormData(form);
    try {
      const response = await apiRequest("POST", "/api/v1/operations/products/", {
        title: values.get("title"), slug: values.get("slug"), category_id: Number(values.get("category")),
        brand_id: values.get("brand") ? Number(values.get("brand")) : null, description: values.get("description"), reason: values.get("reason"),
      });
      if (!response.ok) throw new Error();
      form.reset(); await load();
    } catch { setError("محصول ثبت نشد؛ اطلاعات و تکراری نبودن نشانی را بررسی کنید."); }
    finally { setBusy(false); }
  }
  return <section className="admin-card"><h1>مدیریت محصولات</h1>{error && <p role="alert">{error}</p>}
    <label>جست‌وجو<input value={query} onChange={(event) => { setPage(1); setQuery(event.target.value); }} /></label>
    <h2>محصول جدید</h2><form className="admin-inline-form" onSubmit={create}>
      <label>عنوان<input name="title" required maxLength={240} /></label>
      <label>نشانی محصول<input name="slug" required maxLength={240} /></label>
      <label>دسته<select name="category" required><option value="">انتخاب کنید</option>{categories.map((category) => <option key={category.id} value={category.id}>{category.name}</option>)}</select></label>
      <label>برند<select name="brand"><option value="">بدون برند</option>{brands.filter(brand => brand.is_active).map(brand => <option key={brand.id} value={brand.id}>{brand.name}</option>)}</select></label>
      <label>توضیحات<textarea name="description" /></label>
      <label>دلیل<input name="reason" required minLength={3} maxLength={500} /></label>
      <button disabled={busy}>ساخت پیش‌نویس</button>
    </form><ul className="admin-list">{products.map((product) => <ProductRow key={JSON.stringify(product)} product={product} categories={categories} brands={brands} changed={load} />)}</ul>
    <div className="cart-actions"><button disabled={page === 1} onClick={() => setPage(page - 1)}>قبلی</button><span>صفحهٔ {page}</span><button disabled={!hasNext} onClick={() => setPage(page + 1)}>بعدی</button></div>
  </section>;
}

function ProductRow({ product, categories, brands, changed }: { product: Product; categories: Category[]; brands: Brand[]; changed: () => Promise<void> }) {
  const [notice, setNotice] = useState("");
  const [busy, setBusy] = useState(false);
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); setBusy(true); setNotice("");
    const data = new FormData(event.currentTarget);
    try {
      const response = await apiRequest("PATCH", `/api/v1/operations/products/${product.id}/`, { status: data.get("status"), reason: data.get("reason") });
      if (!response.ok) throw new Error();
      await changed(); setNotice("ذخیره شد.");
    } catch { setNotice("ثبت وضعیت انجام نشد."); } finally { setBusy(false); }
  }
  async function edit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); setBusy(true); const data = new FormData(event.currentTarget);
    try {
      const specifications: Record<string, string> = Object.create(null);
      for (const line of String(data.get("specifications") ?? "").split("\n").filter(line => line.trim())) {
        const split = line.indexOf(":"); if (split < 1) throw new Error();
        const key = line.slice(0, split).trim(), value = line.slice(split + 1).trim();
        if (!key || !value || Object.prototype.hasOwnProperty.call(specifications, key)) throw new Error();
        specifications[key] = value;
      }
      const response = await apiRequest("PATCH", `/api/v1/operations/products/${product.id}/`, { title: data.get("title"), slug: data.get("slug"), category_id: Number(data.get("category")), brand_id: data.get("brand") ? Number(data.get("brand")) : null, description: data.get("description"), specifications, reason: data.get("reason") });
      if (!response.ok) throw new Error(); await changed(); setNotice("اطلاعات ذخیره شد.");
    } catch { setNotice("ذخیره نشد؛ شناسه‌ها، نشانی و قالب مشخصات را بررسی کنید."); } finally { setBusy(false); }
  }
  async function variant(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); setBusy(true); setNotice("");
    const form = event.currentTarget; const data = new FormData(form);
    try {
      const attributes = JSON.parse(String(data.get("attributes") || "{}"));
      const response = await apiRequest("POST", `/api/v1/operations/products/${product.id}/variants/`, { sku: data.get("sku"), attributes, reason: data.get("reason") });
      if (!response.ok) throw new Error();
      form.reset(); setNotice("تنوع محصول ثبت شد.");
    } catch { setNotice("تنوع ثبت نشد؛ SKU و قالب ویژگی‌ها را بررسی کنید."); } finally { setBusy(false); }
  }
  return <li className="admin-record"><div><strong>{product.title}</strong><p>#{product.id} · {product.slug} · {product.status}</p></div>
    <form className="admin-inline-form" onSubmit={submit}><label>وضعیت<select name="status" defaultValue={product.status}><option value="draft">پیش‌نویس</option><option value="published">منتشرشده</option><option value="archived">بایگانی</option></select></label><label>دلیل<input name="reason" required minLength={3} maxLength={500} /></label><button disabled={busy}>ثبت وضعیت</button></form>
    <details><summary>ویرایش اطلاعات محصول</summary><form className="admin-inline-form" onSubmit={edit}><label>عنوان<input name="title" required maxLength={240} defaultValue={product.title}/></label><label>نشانی<input name="slug" required maxLength={240} defaultValue={product.slug}/></label><label>دسته<select name="category" defaultValue={product.category_id}>{categories.map(category => <option key={category.id} value={category.id}>{category.name}</option>)}</select></label><label>برند<select name="brand" defaultValue={product.brand_id ?? ""}><option value="">بدون برند</option>{brands.map(brand => <option key={brand.id} value={brand.id}>{brand.name}{!brand.is_active && " (غیرفعال)"}</option>)}</select></label><label>توضیح<textarea name="description" maxLength={20000} defaultValue={product.description}/></label><label>مشخصات؛ هر خط «عنوان: مقدار»<textarea name="specifications" defaultValue={Object.entries(product.specifications).map(([key, value]) => `${key}: ${value}`).join("\n")}/></label><label>دلیل<input name="reason" required minLength={3} maxLength={500}/></label><button disabled={busy}>ذخیرهٔ اطلاعات</button></form></details>
    <details><summary>افزودن تنوع محصول</summary><form className="admin-inline-form" onSubmit={variant}><label>SKU<input name="sku" required maxLength={80} /></label><label>ویژگی‌ها (JSON)<input name="attributes" defaultValue="{}" dir="ltr" /></label><label>دلیل<input name="reason" required minLength={3} maxLength={500} /></label><button disabled={busy}>افزودن تنوع</button></form></details>
    {notice && <p role="status">{notice}</p>}</li>;
}
