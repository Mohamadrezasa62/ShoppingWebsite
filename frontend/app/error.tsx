"use client";
export default function ErrorPage({ retry }: { retry: () => void }) {
  return <main className="catalog-main"><h1>این صفحه بارگذاری نشد</h1><p>کمی بعد دوباره تلاش کنید.</p><button onClick={() => retry()}>تلاش دوباره</button><p><a href="/">بازگشت به فروشگاه</a></p></main>;
}
