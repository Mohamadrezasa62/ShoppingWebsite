import { cache } from "react";
import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { internalHeaders, internalApi, siteUrl } from "@/lib/site";
const getPage = cache(async (slug: string): Promise<{ title: string; body: string } | null> => {
  const response = await fetch(`${internalApi}/api/v1/operations/content/${encodeURIComponent(slug)}/`, { cache: "no-store", headers: internalHeaders });
  if (response.status === 404) return null;
  if (!response.ok) throw new Error("Content unavailable");
  return (await response.json()).page;
});
export async function generateMetadata({ params }: { params: Promise<{ slug: string }> }): Promise<Metadata> {
  const { slug } = await params;
  try { const page = await getPage(slug); return page ? { title: `${page.title} | ShoppingWebsite`, description: page.body.slice(0, 160), alternates: { canonical: `${siteUrl}/content/${encodeURIComponent(slug)}/` } } : { robots: { index: false } }; }
  catch { return { robots: { index: false } }; }
}
export default async function ContentPage({ params }: { params: Promise<{ slug: string }> }) {
  const page = await getPage((await params).slug);
  if (!page) notFound();
  return <main className="catalog-main"><a href="/content/">راهنماها و قوانین</a><article><h1>{page.title}</h1>{page.body.split("\n").map((line, index) => <p key={index}>{line}</p>)}</article></main>;
}
