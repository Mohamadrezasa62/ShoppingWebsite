import type { MetadataRoute } from "next";
import { internalHeaders, internalApi, siteUrl } from "@/lib/site";
export const dynamic = "force-dynamic";
export default async function sitemap(): Promise<MetadataRoute.Sitemap> {
  const response = await fetch(`${internalApi}/api/v1/catalog/sitemap/`, { cache: "no-store", headers: internalHeaders });
  if (!response.ok) throw new Error("Sitemap catalog unavailable");
  const { products, pages, collections } = await response.json();
  return [{ url: `${siteUrl}/` }, { url: `${siteUrl}/products/` }, { url: `${siteUrl}/content/` },
    { url: `${siteUrl}/collections/` },
    ...collections.map((row: { slug: string; updated_at: string }) => ({ url: `${siteUrl}/collections/${encodeURIComponent(row.slug)}/`, lastModified: row.updated_at })),
    ...products.map((row: { slug: string; updated_at: string }) => ({ url: `${siteUrl}/products/${encodeURIComponent(row.slug)}/`, lastModified: row.updated_at })),
    ...pages.map((row: { slug: string; updated_at: string }) => ({ url: `${siteUrl}/content/${encodeURIComponent(row.slug)}/`, lastModified: row.updated_at }))];
}
