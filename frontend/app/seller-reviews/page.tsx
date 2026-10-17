import { SellerReviewWorkspace } from "@/components/seller-reviews";
export const metadata = { title: "امتیازهای من", robots: { index: false } };
export default function Page() { return <main className="catalog-main"><a href="/orders/">سفارش‌های من</a><SellerReviewWorkspace /></main>; }
