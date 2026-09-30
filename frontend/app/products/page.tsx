import type { Metadata } from "next";
import ProductsBrowser from "./products-browser";

export const metadata: Metadata = {
  title: "جست‌وجوی محصولات | ShoppingWebsite",
  description: "جست‌وجوی محصولات، فیلتر دسته‌بندی و برند، و مقایسهٔ قیمت فروشندگان.",
};

export default function ProductsPage() {
  return <ProductsBrowser />;
}
