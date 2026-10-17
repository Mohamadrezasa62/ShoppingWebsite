"use client";

import { FormEvent, useCallback, useEffect, useState } from "react";
import { AccountClosureWorkspace } from "@/components/account-closure";
import { DisputeWorkspace } from "@/components/dispute-workspace";
import { CampaignWorkspace } from "@/components/campaign-workspace";
import { CatalogImports } from "@/components/catalog-imports";
import { apiRequest } from "@/lib/api";
import { CancellationWorkspace } from "@/components/cancellation-workspace";
import { ReturnsWorkspace } from "@/components/returns-workspace";
import { TaxWorkspace } from "@/components/tax-workspace";
import { ConfigurationWorkspace } from "@/components/configuration-workspace";
import { CollectionWorkspace } from "@/components/collection-workspace";
import { MediaWorkspace } from "@/components/media-workspace";
import { ProductProposals } from "@/components/product-proposals";
import { EventWorkspace } from "@/components/event-workspace";
import { SalesReport } from "@/components/sales-report";
import { PromotionsWorkspace } from "@/components/promotions-workspace";
import { SupportWorkspace } from "@/components/support-workspace";
import { ContentWorkspace } from "@/components/content-workspace";
import { FinanceWorkspace } from "@/components/finance-workspace";
import { CatalogManagement } from "@/components/catalog-management";
import { QuestionModeration } from "@/components/question-moderation";
import { SellerReviewWorkspace } from "@/components/seller-reviews";
import { ReviewImageModeration } from "@/components/review-images";
import { AdminInventory } from "@/components/admin-inventory";
import { RiskWorkspace } from "@/components/risk-workspace";
import { ReviewModeration } from "@/components/review-moderation";
import { AdminOrders } from "@/components/fulfillment-workspace";

type Role = "catalog_operator" | "support_agent" | "finance_operator" | "marketplace_manager" | "system_administrator";
type Tab = "tax" | "inventory" | "risk" | "sellerReviews" | "imports" | "disputes" | "closures" | "overview" | "sellers" | "categories" | "products" | "orders" | "questions" | "reviews" | "cancellations" | "returns" | "finance" | "support" | "content" | "promotions" | "reports" | "staff" | "taxonomy" | "shipping" | "collections" | "media" | "proposals" | "events" | "audit";
type Profile = { id: number; phone: string; can_access_admin: boolean; staff_roles: Role[]; is_superuser: boolean };
type Summary = { pending_sellers: number; approved_sellers: number; categories: number; staff_users: number };
type Seller = { id: number; name: string; legal_name: string; business_identifier: string; contact_phone: string; status: string; review_note: string };
type Category = { id: number; name: string; slug: string; parent_id: number | null; is_active: boolean };
type Staff = { id: number; phone: string; is_staff: boolean; is_superuser: boolean; roles: Role[] };
type AuditEvent = { id: number; created_at: string; actor: string | null; action: string; target_type: string; target_id: string; reason: string };

const roleLabels: Record<Role, string> = {
  catalog_operator: "مدیر کاتالوگ", support_agent: "پشتیبانی", finance_operator: "مالی",
  marketplace_manager: "مدیر بازارگاه", system_administrator: "مدیر سیستم",
};
const allRoles = Object.keys(roleLabels) as Role[];
const tabs: { id: Tab; label: string; roles?: Role[] }[] = [
  { id: "inventory", label: "موجودی انبارها", roles: ["marketplace_manager", "system_administrator"] },
  { id: "risk", label: "ریسک سفارش", roles: ["support_agent", "finance_operator", "marketplace_manager", "system_administrator"] },
  { id: "sellerReviews", label: "امتیاز فروشندگان", roles: ["support_agent", "marketplace_manager", "system_administrator"] },
  { id: "closures", label: "بستن حساب", roles: ["system_administrator"] },
  { id: "disputes", label: "اختلاف سفارش", roles: ["support_agent", "marketplace_manager", "system_administrator"] },
  { id: "imports", label: "ورود گروهی کاتالوگ", roles: ["catalog_operator", "marketplace_manager", "system_administrator"] },
  { id: "overview", label: "نمای کلی" },
  { id: "reports", label: "گزارش‌ها", roles: ["finance_operator", "marketplace_manager", "system_administrator"] },
  { id: "promotions", label: "کوپن‌ها", roles: ["marketplace_manager", "system_administrator"] },
  { id: "support", label: "پشتیبانی", roles: ["support_agent", "marketplace_manager", "system_administrator"] },
  { id: "collections", label: "مجموعه‌ها", roles: ["catalog_operator", "marketplace_manager", "system_administrator"] },
  { id: "content", label: "محتوا", roles: ["catalog_operator", "marketplace_manager", "system_administrator"] },
  { id: "cancellations", label: "لغو ارسال", roles: ["support_agent", "finance_operator", "marketplace_manager", "system_administrator"] },
  { id: "returns", label: "مرجوعی‌ها", roles: ["support_agent", "finance_operator", "marketplace_manager", "system_administrator"] },
  { id: "finance", label: "امور مالی", roles: ["finance_operator", "system_administrator"] },
  { id: "questions", label: "پرسش‌های محصول", roles: ["catalog_operator", "support_agent", "system_administrator"] },
  { id: "reviews", label: "بررسی نظرات", roles: ["catalog_operator", "support_agent", "system_administrator"] },
  { id: "orders", label: "سفارش‌ها", roles: ["support_agent", "marketplace_manager", "system_administrator"] },
  { id: "proposals", label: "محصولات پیشنهادی", roles: ["catalog_operator", "marketplace_manager", "system_administrator"] },
  { id: "media", label: "تصاویر محصول", roles: ["catalog_operator", "marketplace_manager", "system_administrator"] },
  { id: "taxonomy", label: "برند و فیلتر", roles: ["catalog_operator", "marketplace_manager", "system_administrator"] },
  { id: "tax", label: "مالیات دسته‌ها", roles: ["marketplace_manager", "system_administrator"] },
  { id: "shipping", label: "تنظیمات ارسال", roles: ["marketplace_manager", "system_administrator"] },
  { id: "products", label: "محصولات", roles: ["catalog_operator", "marketplace_manager", "system_administrator"] },
  { id: "sellers", label: "فروشندگان", roles: ["marketplace_manager", "system_administrator"] },
  { id: "categories", label: "دسته‌بندی‌ها", roles: ["catalog_operator", "marketplace_manager", "system_administrator"] },
  { id: "staff", label: "کارکنان", roles: ["system_administrator"] },
  { id: "events", label: "سلامت پردازش", roles: ["system_administrator"] },
  { id: "audit", label: "تاریخچهٔ تغییرات", roles: ["system_administrator"] },
];
const sellerChoices: Record<string, string[]> = {
  applied: ["under_review", "approved", "rejected"], under_review: ["approved", "rejected"],
  approved: ["suspended"], suspended: ["approved"], rejected: ["under_review"],
};

async function readJson<T>(path: string): Promise<T> {
  const response = await fetch(path, { credentials: "same-origin" });
  if (!response.ok) throw new Error(response.status === 403 ? "دسترسی به این بخش مجاز نیست." : "دریافت اطلاعات انجام نشد.");
  return response.json();
}

function SellerRow({ seller, changed }: { seller: Seller; changed: () => void }) {
  const [status, setStatus] = useState(sellerChoices[seller.status]?.[0] ?? "");
  const [reason, setReason] = useState("");
  const [message, setMessage] = useState("");
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const response = await apiRequest("POST", `/api/v1/operations/sellers/${seller.id}/decision/`, { status, reason });
    if (response.ok) { setMessage("ثبت شد."); changed(); } else setMessage("ثبت تصمیم انجام نشد.");
  }
  return <li className="admin-record"><div><strong>{seller.name}</strong><p>شناسهٔ {seller.id} · {seller.status}</p><p>{seller.legal_name} · {seller.business_identifier} · <span dir="ltr">{seller.contact_phone}</span></p>{seller.review_note && <p>آخرین دلیل: {seller.review_note}</p>}</div>
    {!!sellerChoices[seller.status]?.length && <form className="admin-inline-form" onSubmit={submit}>
      <label>تصمیم<select value={status} onChange={(event) => setStatus(event.target.value)}>{sellerChoices[seller.status].map((choice) => <option key={choice} value={choice}>{choice}</option>)}</select></label>
      <label>دلیل<input required minLength={3} maxLength={500} value={reason} onChange={(event) => setReason(event.target.value)} /></label>
      <button type="submit">ثبت تصمیم</button>{message && <span role="status">{message}</span>}
    </form>}</li>;
}

function CategoryRow({ category, categories, changed }: { category: Category; categories: Category[]; changed: () => void }) {
  const [editing, setEditing] = useState(false);
  const [name, setName] = useState(category.name);
  const [slug, setSlug] = useState(category.slug);
  const [parentId, setParentId] = useState(category.parent_id?.toString() ?? "");
  const [active, setActive] = useState(category.is_active);
  const [reason, setReason] = useState("");
  const [message, setMessage] = useState("");
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const response = await apiRequest("PATCH", `/api/v1/operations/categories/${category.id}/`, { name, slug, parent_id: parentId ? Number(parentId) : null, is_active: active, reason });
    if (response.ok) { setEditing(false); setMessage("ذخیره شد."); changed(); } else setMessage("ذخیره نشد. اطلاعات را بررسی کنید.");
  }
  return <li className="admin-record"><div><strong>{category.name}</strong><p>{category.slug} · {category.is_active ? "فعال" : "غیرفعال"}</p></div>
    <button type="button" className="admin-secondary" onClick={() => setEditing(!editing)}>{editing ? "بستن" : "ویرایش"}</button>
    {editing && <form className="admin-inline-form" onSubmit={submit}>
      <label>نام<input required value={name} onChange={(event) => setName(event.target.value)} /></label>
      <label>نشانی<input required value={slug} onChange={(event) => setSlug(event.target.value)} /></label>
      <label>بالادست<select value={parentId} onChange={(event) => setParentId(event.target.value)}><option value="">بدون بالادست</option>{categories.filter((item) => item.id !== category.id).map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</select></label>
      <label className="admin-check"><input type="checkbox" checked={active} onChange={(event) => setActive(event.target.checked)} /> فعال</label>
      <label>دلیل<input required minLength={3} maxLength={500} value={reason} onChange={(event) => setReason(event.target.value)} /></label>
      <button type="submit">ذخیره</button>
    </form>}{message && <p role="status">{message}</p>}</li>;
}

function StaffRow({ person, ownId, changed }: { person: Staff; ownId: number; changed: () => void }) {
  const [roles, setRoles] = useState<Role[]>(person.roles);
  const [reason, setReason] = useState("");
  const [message, setMessage] = useState("");
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const response = await apiRequest("POST", `/api/v1/operations/staff/${person.id}/roles/`, { roles, reason });
    if (response.ok) { setMessage("نقش‌ها ذخیره شدند."); changed(); }
    else {
      const result = await response.json();
      setMessage(result.error === "staff_password_setup_required" ? "ابتدا در بخش کاربران Django admin برای این حساب رمز عبور تنظیم کنید." : "تغییر نقش انجام نشد.");
    }
  }
  return <li className="admin-record"><div><strong dir="ltr">{person.phone}</strong><p>{person.is_superuser ? "مدیر اصلی" : person.is_staff ? "کارمند" : "کاربر"}</p></div>
    {person.is_superuser || person.id === ownId ? <p>نقش این حساب از این بخش تغییر نمی‌کند.</p> : <form className="admin-inline-form" onSubmit={submit}>
      <fieldset><legend>نقش‌ها</legend><div className="admin-role-options">{allRoles.map((role) => <label key={role} className="admin-check"><input type="checkbox" checked={roles.includes(role)} onChange={(event) => setRoles(event.target.checked ? [...roles, role] : roles.filter((item) => item !== role))} /> {roleLabels[role]}</label>)}</div></fieldset>
      <label>دلیل<input required minLength={3} maxLength={500} value={reason} onChange={(event) => setReason(event.target.value)} /></label>
      <button type="submit">ذخیرهٔ نقش‌ها</button>{message && <span role="status">{message}</span>}
    </form>}</li>;
}

export function AdminWorkspace() {
  const [profile, setProfile] = useState<Profile | null>(null);
  const [tab, setTab] = useState<Tab>("overview");
  const [summary, setSummary] = useState<Summary | null>(null);
  const [sellers, setSellers] = useState<Seller[]>([]);
  const [categories, setCategories] = useState<Category[]>([]);
  const [staff, setStaff] = useState<Staff[]>([]);
  const [events, setEvents] = useState<AuditEvent[]>([]);
  const [query, setQuery] = useState("");
  const [categoryName, setCategoryName] = useState("");
  const [categoryParent, setCategoryParent] = useState("");
  const [categoryReason, setCategoryReason] = useState("");
  const [notice, setNotice] = useState("");
  const [error, setError] = useState("");

  const load = useCallback(async (selected: Tab, search = "") => {
    setError("");
    try {
      if (selected === "overview") setSummary(await readJson<Summary>("/api/v1/operations/summary/"));
      if (selected === "sellers") setSellers((await readJson<{ sellers: Seller[] }>("/api/v1/operations/sellers/")).sellers);
      if (selected === "categories") setCategories((await readJson<{ categories: Category[] }>("/api/v1/operations/categories/")).categories);
      if (selected === "staff") setStaff((await readJson<{ staff: Staff[] }>(`/api/v1/operations/staff/${search ? `?q=${encodeURIComponent(search)}` : ""}`)).staff);
      if (selected === "audit") setEvents((await readJson<{ events: AuditEvent[] }>("/api/v1/operations/audit/")).events);
    } catch (failure) { setError(failure instanceof Error ? failure.message : "دریافت اطلاعات انجام نشد."); }
  }, []);

  useEffect(() => { readJson<Profile>("/api/v1/auth/me/").then(setProfile).catch(() => setError("برای ورود به پنل مدیریت ابتدا وارد حساب شوید.")); }, []);
  useEffect(() => { if (profile?.can_access_admin) void load(tab); }, [profile, tab, load]);

  function canSee(item: { roles?: Role[] }) {
    return !item.roles || profile?.is_superuser || item.roles.some((role) => profile?.staff_roles.includes(role));
  }

  async function createCategory(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const response = await apiRequest("POST", "/api/v1/operations/categories/", { name: categoryName, parent_id: categoryParent ? Number(categoryParent) : null, reason: categoryReason });
    if (response.ok) { setCategoryName(""); setCategoryParent(""); setCategoryReason(""); setNotice("دسته‌بندی ساخته شد."); void load("categories"); }
    else setNotice("ساخت دسته‌بندی انجام نشد.");
  }

  return <div className="admin-shell">
    <header className="admin-header"><a href="/account/" className="brand">گزیناو</a><span>پنل مدیریت</span>{profile && <span dir="ltr">{profile.phone}</span>}</header>
    {!profile?.can_access_admin ? <main className="admin-main"><section className="admin-card"><h1>دسترسی مدیریت</h1><p>{error || "در حال بررسی دسترسی..."}</p><a href="/login/">ورود</a></section></main> : <div className="admin-layout">
      <nav className="admin-nav" aria-label="بخش‌های مدیریت">{tabs.filter(canSee).map((item) => <button key={item.id} type="button" className={tab === item.id ? "selected" : ""} onClick={() => { setNotice(""); setTab(item.id); }}>{item.label}</button>)}</nav>
      <main className="admin-main">
        {tab === "closures" && <AccountClosureWorkspace admin />}
        {tab === "disputes" && <DisputeWorkspace admin canReview={profile.is_superuser || profile.staff_roles.some((role) => ["marketplace_manager", "system_administrator"].includes(role))} />}
        {tab === "imports" && <CatalogImports />}
        {tab === "products" && <CatalogManagement />}
        {tab === "orders" && <AdminOrders />}
        {tab === "questions" && <QuestionModeration />}
        {tab === "taxonomy" && <><ConfigurationWorkspace mode="brands" /><ConfigurationWorkspace mode="facets" /></>}
        {tab === "tax" && <TaxWorkspace />}
        {tab === "shipping" && <ConfigurationWorkspace mode="shipping" />}
        {tab === "collections" && <CollectionWorkspace />}
        {tab === "media" && <MediaWorkspace />}
        {tab === "proposals" && <ProductProposals />}
        {tab === "events" && <EventWorkspace />}
        {tab === "sellerReviews" && <SellerReviewWorkspace admin />}
        {tab === "reviews" && <><ReviewModeration /><ReviewImageModeration /></>}
        {tab === "cancellations" && <CancellationWorkspace admin />}
        {tab === "returns" && <ReturnsWorkspace admin canRefund={profile.is_superuser || profile.staff_roles.some((role) => ["finance_operator", "system_administrator"].includes(role))} />}
        {tab === "finance" && <FinanceWorkspace />}
        {tab === "inventory" && <AdminInventory />}
        {tab === "risk" && <RiskWorkspace canWrite={profile.is_superuser || profile.staff_roles.some((role) => ["marketplace_manager", "system_administrator"].includes(role))} />}
        {tab === "support" && <SupportWorkspace admin canReviewEscalation={profile.is_superuser || profile.staff_roles.some((role) => ["marketplace_manager", "system_administrator"].includes(role))} />}
        {tab === "content" && <ContentWorkspace />}
        {tab === "promotions" && <><PromotionsWorkspace /><CampaignWorkspace /></>}
        {tab === "reports" && <SalesReport />}
        {error && <p className="admin-alert" role="alert">{error}</p>}{notice && <p className="admin-alert" role="status">{notice}</p>}
        {tab === "overview" && <section className="admin-card"><h1>نمای کلی</h1><div className="admin-metrics">
          <div><strong>{summary?.pending_sellers ?? "—"}</strong><span>فروشنده در انتظار بررسی</span></div><div><strong>{summary?.approved_sellers ?? "—"}</strong><span>فروشندهٔ تأییدشده</span></div>
          <div><strong>{summary?.categories ?? "—"}</strong><span>دسته‌بندی</span></div><div><strong>{summary?.staff_users ?? "—"}</strong><span>کارمند</span></div>
        </div></section>}
        {tab === "sellers" && <section className="admin-card"><h1>فروشندگان</h1><p>وضعیت درخواست‌ها را با ثبت دلیل تغییر دهید.</p><ul className="admin-list">{sellers.map((seller) => <SellerRow key={`${seller.id}-${seller.status}`} seller={seller} changed={() => void load("sellers")} />)}</ul></section>}
        {tab === "categories" && <section className="admin-card"><h1>دسته‌بندی‌ها</h1><form className="admin-inline-form" onSubmit={createCategory}>
          <label>نام دسته<input required value={categoryName} onChange={(event) => setCategoryName(event.target.value)} /></label>
          <label>بالادست<select value={categoryParent} onChange={(event) => setCategoryParent(event.target.value)}><option value="">بدون بالادست</option>{categories.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</select></label>
          <label>دلیل ایجاد<input required minLength={3} maxLength={500} value={categoryReason} onChange={(event) => setCategoryReason(event.target.value)} /></label><button type="submit">افزودن دسته</button>
        </form><ul className="admin-list">{categories.map((category) => <CategoryRow key={category.id} category={category} categories={categories} changed={() => void load("categories")} />)}</ul></section>}
        {tab === "staff" && <section className="admin-card"><h1>کارکنان و نقش‌ها</h1><form className="admin-inline-form" onSubmit={(event) => { event.preventDefault(); void load("staff", query); }}><label>جست‌وجوی شمارهٔ کاربر<input value={query} onChange={(event) => setQuery(event.target.value)} /></label><button type="submit">جست‌وجو</button></form><ul className="admin-list">{staff.map((person) => <StaffRow key={person.id} person={person} ownId={profile.id} changed={() => void load("staff", query)} />)}</ul></section>}
        {tab === "audit" && <section className="admin-card"><h1>تاریخچهٔ تغییرات</h1><ul className="admin-list">{events.map((event) => <li className="admin-record" key={event.id}><div><strong>{event.action}</strong><p>{event.target_type} #{event.target_id} · {event.actor || "حساب حذف‌شده"} · {new Date(event.created_at).toLocaleString("fa-IR")}</p><p>دلیل: {event.reason}</p></div></li>)}</ul></section>}
      </main>
    </div>}
  </div>;
}
