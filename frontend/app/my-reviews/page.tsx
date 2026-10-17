import { MyReviewImages } from "@/components/review-images";
export const metadata = { title: "نظرات من", robots: { index: false } };
export default function Page() { return <main className="catalog-main"><a href="/account/">حساب کاربری</a><MyReviewImages /></main>; }
