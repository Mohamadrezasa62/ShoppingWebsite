import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "ShoppingWebsite",
  description: "بازارگاه چندفروشنده‌ای با جست‌وجوی محصول و مقایسهٔ پیشنهاد فروشندگان",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="fa" dir="rtl">
      <body>{children}</body>
    </html>
  );
}
