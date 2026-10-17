import type { Metadata } from "next";
import "./globals.css";
import "./gozinav.css";
import { AppShell } from "@/components/app-shell";

export const metadata: Metadata = {
  title: { default: "گزیناو | انتخاب روشن، خرید مطمئن", template: "%s | گزیناو" },
  description: "بازارگاه چندفروشنده‌ای با جست‌وجوی محصول و مقایسهٔ پیشنهاد فروشندگان",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="fa" dir="rtl">
      <body><AppShell>{children}</AppShell></body>
    </html>
  );
}
