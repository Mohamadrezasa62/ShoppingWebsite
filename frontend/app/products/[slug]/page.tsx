"use client";

import { use, useEffect, useState } from "react";

type Offer = { id: number; seller: { name: string }; variant: { sku: string; attributes: Record<string, string> }; price_toman: number; warranty: string; fulfillment: string; available_quantity: number };
type Product = { title: string; description: string; specifications: Record<string, string>; category: { name: string }; brand: string | null; offers: Offer[] };

export default function ProductPage({ params }: { params: Promise<{ slug: string }> }) {
  const { slug } = use(params);
  const [product, setProduct] = useState<Product | null>(null);
  const [error, setError] = useState("");
  useEffect(() => {
    fetch(`/api/v1/catalog/products/${encodeURIComponent(slug)}/`).then((response) => {
      if (!response.ok) throw new Error();
      return response.json();
    }).then((data) => setProduct(data.product)).catch(() => setError("این محصول در دسترس نیست."));
  }, [slug]);
  return <div className="catalog-shell"><header className="site-header"><div className="header-inner"><a className="brand" href="/">ShoppingWebsite</a><a href="/products/">همهٔ محصولات</a></div></header><main className="catalog-main">
    {error ? <p role="alert">{error}</p> : !product ? <p>در حال بارگذاری...</p> : <><p>{product.category.name}{product.brand ? ` · ${product.brand}` : ""}</p><h1>{product.title}</h1>{product.description && <p>{product.description}</p>}
      <h2>مشخصات</h2><dl className="product-specs">{Object.entries(product.specifications).map(([key, value]) => <div key={key}><dt>{key}</dt><dd>{String(value)}</dd></div>)}</dl>
      <h2>پیشنهاد فروشندگان</h2><div className="offer-list">{product.offers.map((offer) => <article className="offer-card" key={offer.id}><div><strong>{offer.seller.name}</strong><p>{Object.entries(offer.variant.attributes).map(([key, value]) => `${key}: ${value}`).join(" · ")}</p><p>{offer.warranty || "بدون گارانتی درج‌شده"} · {offer.fulfillment === "seller" ? "ارسال فروشنده" : "ارسال پلتفرم"}</p></div><div><b>{offer.price_toman.toLocaleString("fa-IR")} تومان</b><p>{offer.available_quantity.toLocaleString("fa-IR")} عدد موجود</p></div></article>)}</div>
      <p className="catalog-note">امکان ثبت سفارش در مرحلهٔ سبد خرید اضافه می‌شود.</p></>}
  </main></div>;
}
