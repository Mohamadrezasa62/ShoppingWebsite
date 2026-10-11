"use client";

import { useEffect, useState } from "react";
import { StaffPassword } from "@/components/staff-password";
import { AccountClosureWorkspace } from "@/components/account-closure";
import { NotificationPreferences } from "@/components/campaign-workspace";
import { apiRequest } from "@/lib/api";

type Profile = {
  phone: string;
  first_name: string;
  last_name: string;
  is_staff: boolean;
  can_access_admin: boolean;
  seller_memberships: { seller_id: number; seller__name: string; seller__status: string; role: string }[];
};

export default function AccountPage() {
  const [profile, setProfile] = useState<Profile | null>(null);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [busy, setBusy] = useState(false);

  async function save(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault(); setBusy(true); setNotice("");
    const data = new FormData(event.currentTarget);
    try {
      const response = await apiRequest("PATCH", "/api/v1/auth/me/", { first_name: data.get("first_name"), last_name: data.get("last_name") });
      if (!response.ok) throw new Error();
      setProfile(await response.json()); setNotice("پروفایل ذخیره شد.");
    } catch { setNotice("ذخیره انجام نشد."); } finally { setBusy(false); }
  }
  async function logout(all = false) {
    setBusy(true);
    try {
      const response = await apiRequest("POST", all ? "/api/v1/auth/revoke-sessions/" : "/api/v1/auth/logout/");
      if (!response.ok) throw new Error();
      window.location.assign("/login/");
    } catch { setNotice("خروج انجام نشد."); setBusy(false); }
  }

  useEffect(() => {
    fetch("/api/v1/auth/me/", { credentials: "same-origin" })
      .then(async (response) => {
        if (!response.ok) throw new Error("Please sign in");
        return response.json();
      })
      .then(setProfile)
      .catch(() => setError("برای مشاهدهٔ حساب وارد شوید."));
  }, []);

  return <main className="form-page"><section className="form-card">
    <a href="/" className="brand">ShoppingWebsite</a>
    <h1>حساب کاربری</h1>
    {error ? <><p>{error}</p><a href="/login">ورود</a></> : profile ? <>
      <p>شمارهٔ موبایل: <span dir="ltr">{profile.phone}</span></p>
      <form className="admin-inline-form" onSubmit={save}><label>نام<input name="first_name" defaultValue={profile.first_name} maxLength={150} /></label><label>نام خانوادگی<input name="last_name" defaultValue={profile.last_name} maxLength={150} /></label><button disabled={busy}>ذخیرهٔ پروفایل</button></form>
      {notice && <p role="status">{notice}</p>}
      <nav className="account-links" aria-label="بخش‌های حساب">
        <a href="/my-reviews/">نظرات و تصاویر من</a><a href="/seller-reviews/">امتیازهای من</a><a href="/following/">دنبال‌شده‌ها</a><a href="/recently-viewed/">اخیراً دیده‌شده‌ها</a><a href="/alerts/">اعلان‌های محصول</a><a href="/api/v1/auth/export/">دریافت اطلاعات حساب</a><a href="/disputes/">اختلاف‌های سفارش</a><a href="/support/">پشتیبانی</a><a href="/notifications/">اعلان‌ها</a><a href="/content/">راهنماها</a><a href="/wishlist/">علاقه‌مندی‌ها</a><a href="/orders/">سفارش‌های من</a><a href="/cart/">سبد خرید</a>
        {profile.seller_memberships.some((item) => item.seller__status === "approved") && <a href="/seller-panel">پنل فروشنده</a>}
        {profile.can_access_admin && <a href="/admin-panel">پنل مدیریت</a>}
      </nav>
      <button disabled={busy} onClick={() => void logout()}>خروج از حساب</button><button disabled={busy} onClick={() => { if (window.confirm("از همهٔ دستگاه‌ها خارج شوید؟")) void logout(true); }}>خروج از همهٔ دستگاه‌ها</button>
      {profile.is_staff && <StaffPassword />}
      <NotificationPreferences /><AccountClosureWorkspace />
    </> : <p>در حال بارگذاری...</p>}
  </section></main>;
}
