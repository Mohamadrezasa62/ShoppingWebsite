import type { Metadata } from "next";
import ProductView from "./product-view";
import { notFound } from "next/navigation";
import { getProduct } from "@/lib/catalog";
import { siteUrl } from "@/lib/site";

export async function generateMetadata({ params }: { params: Promise<{ slug: string }> }): Promise<Metadata> {
  const { slug } = await params;
  try {
    const product = await getProduct(slug);
    if (!product) return { title: "محصول در دسترس نیست | ShoppingWebsite", robots: { index: false } };
    const description = product.description?.slice(0, 160) || `مقایسهٔ قیمت و فروشندگان ${product.title}`;
    return { title: `${product.title} | ShoppingWebsite`, description, alternates: { canonical: `${siteUrl}/products/${encodeURIComponent(slug)}/` }, openGraph: { title: product.title, description } };
  } catch {
    return { title: "ShoppingWebsite", robots: { index: false } };
  }
}

export default async function ProductPage({ params }: { params: Promise<{ slug: string }> }) {
  const product = await getProduct((await params).slug);
  if (!product) notFound();
  return <ProductView params={params} initialProduct={product} />;
}
