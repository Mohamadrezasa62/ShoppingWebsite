"use client";

import { useEffect, useState } from "react";

type Profile = {
  phone: string;
  is_staff: boolean;
  can_access_admin: boolean;
  seller_memberships: { seller_id: number; seller__name: string; seller__status: string; role: string }[];
};

export default function AccountPage() {
  const [profile, setProfile] = useState<Profile | null>(null);
  const [error, setError] = useState("");

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
      <nav className="account-links" aria-label="بخش‌های حساب">
        {profile.seller_memberships.some((item) => item.seller__status === "approved") && <a href="/seller-panel">پنل فروشنده</a>}
        {profile.can_access_admin && <a href="/admin-panel">پنل مدیریت</a>}
      </nav>
    </> : <p>در حال بارگذاری...</p>}
  </section></main>;
}
