"use client";

import { FormEvent, useEffect, useRef, useState } from "react";

type Category = { id: number; name: string; slug: string };
type Brand = { name: string; slug: string };
type Facet = { key: string; label: string; choices: string[] };
type Suggestion = { title: string; slug: string };
type Product = { id: number; title: string; slug: string; category: string; brand: string | null; starting_price_toman: number; image: { url: string; alt: string } | null };

export default function ProductsBrowser() {
  const filterPanel = useRef<HTMLDetailsElement>(null);
  const [categories, setCategories] = useState<Category[]>([]);
  const [brands, setBrands] = useState<Brand[]>([]);
  const [facets, setFacets] = useState<Facet[]>([]);
  const [facetValues, setFacetValues] = useState<Record<string, string>>({});
  const [suggestions, setSuggestions] = useState<Suggestion[]>([]);
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
  useEffect(() => {
    if (!category) { setFacets([]); return; }
    const controller = new AbortController();
    fetch(`/api/v1/catalog/facets/?category=${encodeURIComponent(category)}`, { signal: controller.signal })
      .then((response) => response.json()).then((data) => setFacets(data.facets ?? []))
      .catch((failure) => { if (failure.name !== "AbortError") setError("فیلترهای دسته‌بندی بارگذاری نشدند."); });
    return () => controller.abort();
  }, [category]);
  useEffect(() => {
    if (query.trim().length < 2) { setSuggestions([]); return; }
    const controller = new AbortController();
    const timer = setTimeout(() => {
      fetch(`/api/v1/catalog/suggestions/?q=${encodeURIComponent(query)}`, { signal: controller.signal })
        .then((response) => response.json()).then((data) => setSuggestions(data.suggestions ?? []))
        .catch((failure) => { if (failure.name !== "AbortError") setSuggestions([]); });
    }, 250);
    return () => { clearTimeout(timer); controller.abort(); };
  }, [query]);
  async function load(nextPage: number, nextQuery = query, nextCategory = category, nextBrand = brand, nextMinPrice = minPrice, nextMaxPrice = maxPrice, nextSort = sort, nextFacetValues = facetValues) {
    setLoading(true); setError("");
    const params = new URLSearchParams({ page: String(nextPage), q: nextQuery, category: nextCategory, brand: nextBrand, min_price: nextMinPrice, max_price: nextMaxPrice, sort: nextSort });
    for (const [key, value] of Object.entries(nextFacetValues)) if (value) params.set(`facet_${key}`, value);
    try {
      const response = await fetch(`/api/v1/catalog/products/?${params}`);
      if (!response.ok) throw new Error();
      const data = await response.json();
      setProducts(data.products); setPage(nextPage); setHasNext(data.has_next);
    } catch { setError("محصولات بارگذاری نشدند."); }
    finally { setLoading(false); }
  }
  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const initialQuery = params.get("q")?.slice(0, 120) ?? "";
    const initialCategory = params.get("category") ?? "";
    setQuery(initialQuery); setCategory(initialCategory);
    void load(1, initialQuery, initialCategory, "", "", "", "relevance", {});
    const mobile = window.matchMedia("(max-width: 600px)");
    const resize = () => { if (filterPanel.current) filterPanel.current.open = !mobile.matches; };
    resize(); mobile.addEventListener("change", resize);
    return () => mobile.removeEventListener("change", resize);
  }, []);
  function submit(event: FormEvent<HTMLFormElement>) { event.preventDefault(); setSuggestions([]); if (minPrice && maxPrice && Number(minPrice) > Number(maxPrice)) { setError("حداقل قیمت از حداکثر بیشتر است."); return; } void load(1); }
  return <div className="catalog-shell"><header className="site-header"><div className="header-inner"><a className="brand" href="/">گزیناو</a><a href="/login/">ورود / ثبت‌نام</a></div></header>
    <main className="catalog-main"><h1>محصولات</h1><details className="gz-filter-panel" ref={filterPanel} open><summary>فیلترها و مرتب‌سازی</summary><form className="catalog-filters" onSubmit={submit}>
      <label>جست‌وجو<input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="نام محصول یا برند" autoComplete="off" />{suggestions.length > 0 && <ul className="catalog-suggestions">{suggestions.map((item) => <li key={item.slug}><a href={`/products/${encodeURIComponent(item.slug)}/`}>{item.title}</a></li>)}</ul>}</label>
      <label>دسته‌بندی<select value={category} onChange={(event) => { setCategory(event.target.value); setFacetValues({}); }}><option value="">همهٔ دسته‌ها</option>{categories.map((item) => <option key={item.id} value={item.slug}>{item.name}</option>)}</select></label>
      {facets.map((facet) => <label key={facet.key}>{facet.label}<select value={facetValues[facet.key] ?? ""} onChange={(event) => setFacetValues({ ...facetValues, [facet.key]: event.target.value })}><option value="">همه</option>{facet.choices.map((choice) => <option key={choice} value={choice}>{choice}</option>)}</select></label>)}
      <label>برند<select value={brand} onChange={(event) => setBrand(event.target.value)}><option value="">همهٔ برندها</option>{brands.map((item) => <option key={item.slug} value={item.slug}>{item.name}</option>)}</select></label>
      <label>حداقل قیمت (تومان)<input type="number" min="0" value={minPrice} onChange={(event) => setMinPrice(event.target.value)} /></label>
      <label>حداکثر قیمت (تومان)<input type="number" min="0" value={maxPrice} onChange={(event) => setMaxPrice(event.target.value)} /></label>
      <label>ترتیب<select value={sort} onChange={(event) => setSort(event.target.value)}><option value="relevance">جدیدترین</option><option value="price_asc">ارزان‌ترین</option><option value="price_desc">گران‌ترین</option></select></label>
      <button type="submit">اعمال فیلترها</button></form></details>
      {error && <p role="alert">{error}</p>}{loading ? <p>در حال بارگذاری...</p> : products.length ? <div className="product-grid">{products.map((item) => <a className="product-card" href={`/products/${encodeURIComponent(item.slug)}/`} key={item.id}>{item.image && <img className="product-thumb" src={item.image.url} alt={item.image.alt} loading="lazy" />}<span>{item.category}{item.brand ? ` · ${item.brand}` : ""}</span><strong>{item.title}</strong><b>{item.starting_price_toman.toLocaleString("fa-IR")} تومان</b></a>)}</div> : <p>محصولی با این جست‌وجو پیدا نشد.</p>}
      <div className="catalog-pages"><button type="button" disabled={page <= 1 || loading} onClick={() => void load(page - 1)}>صفحهٔ قبل</button><span>صفحهٔ {page.toLocaleString("fa-IR")}</span><button type="button" disabled={!hasNext || loading} onClick={() => void load(page + 1)}>صفحهٔ بعد</button></div>
    </main></div>;
}
