import { cache } from "react";
import type { Product } from "@/app/products/[slug]/product-view";
import { internalHeaders, internalApi } from "@/lib/site";
export const getProduct = cache(async (slug: string): Promise<Product | null> => {
  const response = await fetch(`${internalApi}/api/v1/catalog/products/${encodeURIComponent(slug)}/`, { cache: "no-store", headers: internalHeaders });
  if (response.status === 404) return null;
  if (!response.ok) throw new Error("Catalog unavailable");
  return (await response.json()).product;
});
