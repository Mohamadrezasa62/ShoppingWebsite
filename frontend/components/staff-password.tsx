"use client";
import { FormEvent, useState } from "react";
import { apiRequest } from "@/lib/api";
export function StaffPassword() {
  const [sent, setSent] = useState(false); const [busy, setBusy] = useState(false); const [notice, setNotice] = useState("");
  async function requestCode() {
    setBusy(true); setNotice("");
    try {
      const response = await apiRequest("POST", "/api/v1/auth/staff-password/request-code/");
      if (response.status === 429) { setNotice("کمی بعد دوباره درخواست کنید."); return; }
      if (!response.ok) throw new Error(); setSent(true); setNotice("کد اختصاصی تغییر رمز به شمارهٔ حساب ارسال شد.");
    } catch { setNotice("کد ارسال نشد؛ دسترسی حساب و سرویس پیامک را بررسی کنید."); } finally { setBusy(false); }
  }
  async function change(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); const form = event.currentTarget; const data = new FormData(form);
    if (data.get("new_password") !== data.get("confirm_password")) { setNotice("رمز تازه و تکرار آن یکسان نیستند."); return; }
    setBusy(true); setNotice("");
    try {
      const response = await apiRequest("POST", "/api/v1/auth/staff-password/change/", {current_password: data.get("current_password"), new_password: data.get("new_password"), code: data.get("code")});
      const result = await response.json();
      if (!response.ok) {
        setNotice(result.error === "weak_password" ? "رمز تازه کوتاه، رایج یا بیش از حد شبیه اطلاعات حساب است." : result.error === "password_unchanged" ? "رمز تازه باید با رمز فعلی تفاوت داشته باشد." : response.status === 429 ? "کمی بعد دوباره تلاش کنید." : "تغییر انجام نشد؛ رمز فعلی و کد اختصاصی را بررسی کنید. اگر کد مصرف یا منقضی شده، کد تازه بگیرید.");
        return;
      }
      form.reset(); setSent(false); setNotice("رمز تغییر کرد و نشست‌های قبلی باطل شدند. دوباره وارد شوید.");
      window.location.assign("/login/");
    } catch { setNotice("نتیجهٔ درخواست دریافت نشد؛ ابتدا ورود با رمز تازه را بررسی کنید."); } finally { setBusy(false); }
  }
  return <details><summary>تغییر رمز کارکنان</summary><p>رمز فعلی و کد اختصاصی تغییر رمز لازم است. این بخش بازیابی رمز فراموش‌شده نیست. پس از موفقیت باید در همهٔ دستگاه‌ها دوباره وارد شوید.</p><button type="button" disabled={busy} onClick={() => void requestCode()}>دریافت کد تغییر رمز</button>{sent && <form className="admin-inline-form" onSubmit={change}><label>رمز فعلی<input name="current_password" type="password" autoComplete="current-password" required maxLength={1024} /></label><label>رمز تازه<input name="new_password" type="password" autoComplete="new-password" required minLength={8} maxLength={1024} /></label><label>تکرار رمز تازه<input name="confirm_password" type="password" autoComplete="new-password" required maxLength={1024} /></label><label>کد تغییر رمز<input name="code" inputMode="numeric" autoComplete="one-time-code" required maxLength={6} /></label><button disabled={busy}>تغییر رمز و خروج از دستگاه‌ها</button></form>}{notice && <p role="status">{notice}</p>}</details>;
}
