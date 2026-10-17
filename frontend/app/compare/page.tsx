import { ProductComparison } from "@/components/product-comparison";
export const metadata = { title: "مقایسهٔ محصولات", robots: { index: false } };
export default function Page() { return <main className="catalog-main"><a href="/products/">محصولات</a><ProductComparison /></main>; }
