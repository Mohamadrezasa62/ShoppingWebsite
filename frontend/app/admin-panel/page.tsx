import { PortalAccess } from "@/components/portal-access";

export default function AdminPanelPage() {
  return <PortalAccess title="پنل مدیریت" endpoint="/api/v1/admin/overview/" />;
}
