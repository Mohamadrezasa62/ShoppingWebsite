import type { Metadata } from "next";
import ProductView from "./product-view";

export async function generateMetadata({ params }: { params: Promise<{ slug: string }> }): Promise<Metadata> {
  const { slug } = await params;
  const api = process.env.API_INTERNAL_URL ?? "http://localhost:8000";
  try {
    const response = await fetch(`${api}/api/v1/catalog/products/${encodeURIComponent(slug)}/`, { cache: "no-store" });
    if (!response.ok) return { title: "محصول در دسترس نیست | ShoppingWebsite", robots: { index: false } };
    const { product } = await response.json();
    const description = product.description?.slice(0, 160) || `مقایسهٔ قیمت و فروشندگان ${product.title}`;
    return { title: `${product.title} | ShoppingWebsite`, description, openGraph: { title: product.title, description } };
  } catch {
    return { title: "ShoppingWebsite", robots: { index: false } };
  }
}

export default function ProductPage({ params }: { params: Promise<{ slug: string }> }) {
  return <ProductView params={params} />;
}
