"use client";

import { use, useEffect, useState } from "react";
import { apiRequest } from "@/lib/api";
import { ProductTrust } from "@/components/product-trust";

type Offer = { id: number; seller: { id: number; name: string }; variant: { id: number; sku: string; attributes: Record<string, string> }; price_toman: number; warranty: string; fulfillment: string; available_quantity: number };
export type Product = { slug: string; id: number; title: string; description: string; specifications: Record<string, string>; category: { name: string }; brand: string | null; brand_id: number | null; images: { url: string; alt: string }[]; offers: Offer[] };

export default function ProductView({ params, initialProduct }: { params: Promise<{ slug: string }>; initialProduct?: Product }) {
  const { slug } = use(params);
  const [product, setProduct] = useState<Product | null>(initialProduct ?? null);
  const [selectedVariantId, setSelectedVariantId] = useState<number | null>(initialProduct?.offers[0]?.variant.id ?? null);
  const [error, setError] = useState("");
  const [cartNotice, setCartNotice] = useState("");
  useEffect(() => {
    if (initialProduct?.slug === slug) { setProduct(initialProduct); setSelectedVariantId(initialProduct.offers[0]?.variant.id ?? null); return; }
    fetch(`/api/v1/catalog/products/${encodeURIComponent(slug)}/`).then((response) => {
      if (!response.ok) throw new Error();
      return response.json();
    }).then((data) => { setProduct(data.product); setSelectedVariantId(data.product.offers[0]?.variant.id ?? null); }).catch(() => setError("این محصول در دسترس نیست."));
  }, [slug, initialProduct]);
  useEffect(() => {
    if (!product) return;
    let active = true;
    fetch("/api/v1/auth/me/", { credentials: "same-origin" }).then(async (response) => {
      if (!response.ok) return;
      const profile = await response.json();
      if (active && profile.browsing_history_enabled) await apiRequest("POST", "/api/v1/catalog/history/views/", { product_id: product.id });
    }).catch(() => { /* Optional history must not interrupt shopping. */ });
    return () => { active = false; };
  }, [product]);
  const variants = product ? Array.from(new Map(product.offers.map((offer) => [offer.variant.id, offer.variant])).values()) : [];
  const matchingOffers = product?.offers.filter((offer) => offer.variant.id === selectedVariantId) ?? [];
  async function addToCart(offerId: number) {
    const response = await apiRequest("POST", "/api/v1/commerce/cart/", { offer_id: offerId, quantity: 1 });
    if (response.ok) setCartNotice("به سبد خرید اضافه شد.");
    else if (response.status === 401) setCartNotice("برای افزودن به سبد خرید وارد حساب شوید.");
    else setCartNotice("این پیشنهاد اکنون قابل افزودن نیست.");
  }
  async function follow(kind: "brand" | "seller", targetId: number) {
    try {
      const response = await apiRequest("POST", "/api/v1/catalog/following/", { kind, target_id: targetId });
      setCartNotice(response.ok ? "دنبال شد؛ محصولات را در بخش دنبال‌شده‌های حساب ببینید." : response.status === 401 ? "برای دنبال‌کردن وارد حساب شوید." : "دنبال‌کردن اکنون ممکن نیست.");
    } catch { setCartNotice("ارتباط برقرار نشد."); }
  }
  return <div className="catalog-shell"><header className="site-header"><div className="header-inner"><a className="brand" href="/">گزیناو</a><a href="/products/">همهٔ محصولات</a><a href="/cart/">سبد خرید</a></div></header><main className="catalog-main">
    {error ? <p role="alert">{error}</p> : !product ? <p>در حال بارگذاری...</p> : <><p>{product.category.name}{product.brand ? ` · ${product.brand}` : ""}</p><h1>{product.title}</h1>{product.brand_id && <button onClick={() => void follow("brand", product.brand_id!)}>دنبال‌کردن برند {product.brand}</button>}{product.images.length > 0 && <div className="product-gallery">{product.images.map((image) => <img key={image.url} src={image.url} alt={image.alt} loading="lazy" />)}</div>}{product.description && <p>{product.description}</p>}
      <a href={`/compare/?ids=${product.id}`}>مقایسه با محصول دیگر</a><h2>مشخصات</h2><dl className="product-specs">{Object.entries(product.specifications).map(([key, value]) => <div key={key}><dt>{key}</dt><dd>{String(value)}</dd></div>)}</dl>
      <h2>انتخاب مدل</h2><div className="variant-options">{variants.map((variant) => <button type="button" key={variant.id} aria-pressed={selectedVariantId === variant.id} onClick={() => setSelectedVariantId(variant.id)}>{Object.entries(variant.attributes).map(([key, value]) => `${key}: ${value}`).join(" · ") || variant.sku}</button>)}</div>
      <h2>پیشنهاد فروشندگان</h2>{cartNotice && <p role="status">{cartNotice}</p>}<div className="offer-list">{matchingOffers.map((offer) => <article className="offer-card" key={offer.id}><div><a href={`/sellers/${offer.seller.id}/`}><strong>{offer.seller.name}</strong> · امتیاز خریداران</a><button onClick={() => void follow("seller", offer.seller.id)}>دنبال‌کردن فروشنده</button><p>{offer.warranty || "بدون گارانتی درج‌شده"} · {offer.fulfillment === "seller" ? "ارسال فروشنده" : "ارسال پلتفرم"}</p></div><div><b>{offer.price_toman.toLocaleString("fa-IR")} تومان</b><p>{offer.available_quantity.toLocaleString("fa-IR")} عدد موجود</p><button type="button" className="catalog-action" onClick={() => void addToCart(offer.id)}>افزودن به سبد</button></div></article>)}</div>
      <ProductTrust key={product.id} productId={product.id} /><p className="catalog-note">مبلغ نهایی و زمان تحویل در مرحلهٔ پرداخت مشخص می‌شود.</p></>}
  </main></div>;
}
