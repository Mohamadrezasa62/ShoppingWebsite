import { internalHeaders, internalApi } from "@/lib/site";
export const dynamic = "force-dynamic";
export default async function CollectionsPage() {
  const response = await fetch(`${internalApi}/api/v1/catalog/collections/`, {cache:"no-store",headers:internalHeaders});
  if (!response.ok) throw new Error("Collections unavailable");
  const rows: {title:string; slug:string; description:string}[] = (await response.json()).collections;
  return <main className="catalog-main"><a href="/">فروشگاه</a><h1>مجموعه‌های منتخب</h1><ul className="admin-list">{rows.map(row => <li key={row.slug}><h2><a href={`/collections/${encodeURIComponent(row.slug)}/`}>{row.title}</a></h2><p>{row.description}</p></li>)}</ul>{!rows.length && <p>مجموعه‌ای منتشر نشده است.</p>}</main>;
}
