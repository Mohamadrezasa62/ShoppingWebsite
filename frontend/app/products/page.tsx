"use client";

import { FormEvent, useEffect, useState } from "react";

type Category = { id: number; name: string; slug: string };
type Brand = { name: string; slug: string };
type Product = { id: number; title: string; slug: string; category: string; brand: string | null; starting_price_toman: number; image: { url: string; alt: string } | null };

export default function ProductsPage() {
  const [categories, setCategories] = useState<Category[]>([]);
  const [brands, setBrands] = useState<Brand[]>([]);
  const [products, setProducts] = useState<Product[]>([]);
  const [query, setQuery] = useState("");
  const [category, setCategory] = useState("");
  const [brand, setBrand] = useState("");
  const [minPrice, setMinPrice] = useState("");
  const [maxPrice, setMaxPrice] = useState("");
  const [sort, setSort] = useState("relevance");
  const [page, setPage] = useState(1);
  const [hasNext, setHasNext] = useState(false);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  useEffect(() => { fetch("/api/v1/catalog/categories/").then((response) => response.json()).then((data) => setCategories(data.categories ?? [])).catch(() => setError("دسته‌بندی‌ها بارگذاری نشدند.")); }, []);
  useEffect(() => { fetch("/api/v1/catalog/brands/").then((response) => response.json()).then((data) => setBrands(data.brands ?? [])).catch(() => setError("برندها بارگذاری نشدند.")); }, []);
  async function load(nextPage: number, nextQuery = query, nextCategory = category, nextBrand = brand, nextMinPrice = minPrice, nextMaxPrice = maxPrice, nextSort = sort) {
    setLoading(true); setError("");
    const params = new URLSearchParams({ page: String(nextPage), q: nextQuery, category: nextCategory, brand: nextBrand, min_price: nextMinPrice, max_price: nextMaxPrice, sort: nextSort });
    try {
      const response = await fetch(`/api/v1/catalog/products/?${params}`);
      if (!response.ok) throw new Error();
      const data = await response.json();
      setProducts(data.products); setPage(nextPage); setHasNext(data.has_next);
    } catch { setError("محصولات بارگذاری نشدند."); }
    finally { setLoading(false); }
  }
  useEffect(() => { void load(1, "", "", "", "", "", "relevance"); }, []); // Initial public catalog load.
  function submit(event: FormEvent<HTMLFormElement>) { event.preventDefault(); if (minPrice && maxPrice && Number(minPrice) > Number(maxPrice)) { setError("حداقل قیمت از حداکثر بیشتر است."); return; } void load(1); }
  return <div className="catalog-shell"><header className="site-header"><div className="header-inner"><a className="brand" href="/">ShoppingWebsite</a><a href="/login/">ورود / ثبت‌نام</a></div></header>
    <main className="catalog-main"><h1>محصولات</h1><form className="catalog-filters" onSubmit={submit}>
      <label>جست‌وجو<input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="نام محصول یا برند" /></label>
      <label>دسته‌بندی<select value={category} onChange={(event) => setCategory(event.target.value)}><option value="">همهٔ دسته‌ها</option>{categories.map((item) => <option key={item.id} value={item.slug}>{item.name}</option>)}</select></label>
      <label>برند<select value={brand} onChange={(event) => setBrand(event.target.value)}><option value="">همهٔ برندها</option>{brands.map((item) => <option key={item.slug} value={item.slug}>{item.name}</option>)}</select></label>
      <label>حداقل قیمت (تومان)<input type="number" min="0" value={minPrice} onChange={(event) => setMinPrice(event.target.value)} /></label>
      <label>حداکثر قیمت (تومان)<input type="number" min="0" value={maxPrice} onChange={(event) => setMaxPrice(event.target.value)} /></label>
      <label>ترتیب<select value={sort} onChange={(event) => setSort(event.target.value)}><option value="relevance">جدیدترین</option><option value="price_asc">ارزان‌ترین</option><option value="price_desc">گران‌ترین</option></select></label>
      <button type="submit">اعمال</button></form>
      {error && <p role="alert">{error}</p>}{loading ? <p>در حال بارگذاری...</p> : products.length ? <div className="product-grid">{products.map((item) => <a className="product-card" href={`/products/${encodeURIComponent(item.slug)}/`} key={item.id}>{item.image && <img className="product-thumb" src={item.image.url} alt={item.image.alt} loading="lazy" />}<span>{item.category}{item.brand ? ` · ${item.brand}` : ""}</span><strong>{item.title}</strong><b>{item.starting_price_toman.toLocaleString("fa-IR")} تومان</b></a>)}</div> : <p>محصولی با این جست‌وجو پیدا نشد.</p>}
      <div className="catalog-pages"><button type="button" disabled={page <= 1 || loading} onClick={() => void load(page - 1)}>صفحهٔ قبل</button><span>صفحهٔ {page.toLocaleString("fa-IR")}</span><button type="button" disabled={!hasNext || loading} onClick={() => void load(page + 1)}>صفحهٔ بعد</button></div>
    </main></div>;
}
