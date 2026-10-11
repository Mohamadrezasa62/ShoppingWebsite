import type { MetadataRoute } from "next";
import { siteUrl } from "@/lib/site";
export default function robots(): MetadataRoute.Robots {
  return { rules: { userAgent: "*", allow: "/", disallow: ["/api/", "/admin-panel/", "/seller-panel/", "/alerts/", "/following/", "/seller-reviews/", "/my-reviews/", "/compare/", "/account/", "/cancellations/", "/cart/", "/login/", "/orders/", "/returns/", "/disputes/", "/notifications/", "/support/", "/wishlist/", "/sandbox-payment/"] }, sitemap: `${siteUrl}/sitemap.xml` };
}
