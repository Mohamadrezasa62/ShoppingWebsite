"use client";
import { useEffect, useState } from "react";
export default function ContentIndex() {
  const [pages, setPages] = useState<{ title: string; slug: string; kind: string }[]>([]);
  const [error, setError] = useState("");
  useEffect(() => { fetch("/api/v1/operations/content/").then(async (response) => { if (!response.ok) throw new Error(); setPages((await response.json()).pages); }).catch(() => setError("محتوا دریافت نشد.")); }, []);
  return <main className="catalog-main"><a href="/">فروشگاه</a><h1>راهنماها و قوانین</h1>{error && <p role="alert">{error}</p>}<ul>{pages.map((page) => <li key={page.slug}><a href={`/content/${encodeURIComponent(page.slug)}/`}>{page.title}</a></li>)}</ul></main>;
}
