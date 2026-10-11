import { notFound } from "next/navigation";
import { PublicSellerReviews } from "@/components/seller-reviews";
export const metadata = { title: "امتیاز فروشنده | ShoppingWebsite", robots: { index: false } };
export default async function SellerPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  if (!/^\d+$/.test(id) || !Number.isSafeInteger(Number(id)) || Number(id) < 1) notFound();
  return <main className="catalog-main"><a href="/products/">محصولات</a><PublicSellerReviews sellerId={Number(id)} /></main>;
}
