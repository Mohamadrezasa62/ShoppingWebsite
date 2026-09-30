import { PortalAccess } from "@/components/portal-access";

export default function SellerPanelPage() {
  return <PortalAccess title="پنل فروشنده" endpoint="/api/v1/seller/stores/" />;
}
