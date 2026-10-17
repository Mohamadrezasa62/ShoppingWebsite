"use client";
import { FormEvent, useState } from "react";
import { useRouter } from "next/navigation";
import { apiPost } from "@/lib/api";
import { Brand, BrandMark } from "@/components/brand";
import { UiIcon } from "@/components/ui-icon";

const errors: Record<string, string> = {
  invalid_credentials: "ایمیل یا رمز عبور درست نیست.", invalid_phone: "شمارهٔ موبایل معتبر وارد کن.",
  invalid_registration: "ایمیل را بررسی کن و رمز قوی‌تری انتخاب کن؛ رمز نباید رایج یا شبیه اطلاعات حسابت باشد.",
  email_unavailable: "ثبت‌نام با این ایمیل ممکن نیست. اگر حساب داری، وارد شو.",
  invalid_code: "کد تأیید نادرست یا منقضی شده است.", invalid_request: "اطلاعات واردشده را بررسی کن.",
  invalid_staff_credentials: "کد تأیید یا رمز کارکنان درست نیست.",
  staff_phone_verification_required: "برای ورود کارکنان، روش موبایل را انتخاب کن و همراه کد تأیید، رمز عبورت را وارد کن.",
  sms_unavailable: "ارسال پیامک فعلاً در دسترس نیست؛ می‌توانی با حساب ایمیلی وارد شوی.",
  authentication_unavailable: "سرویس ورود موقتاً در دسترس نیست. کمی بعد دوباره تلاش کن.",
  account_unavailable: "ورود به این حساب در دسترس نیست.", rate_limited: "تعداد تلاش‌ها زیاد است. کمی بعد دوباره تلاش کن.",
};
export default function LoginPage() {
  const router = useRouter();
  const [method, setMethod] = useState<"email" | "phone">("email");
  const [register, setRegister] = useState(false), [step, setStep] = useState<"phone" | "code">("phone");
  const [phone, setPhone] = useState(""), [email, setEmail] = useState(""), [name, setName] = useState("");
  const [code, setCode] = useState(""), [password, setPassword] = useState(""), [confirmation, setConfirmation] = useState("");
  const [message, setMessage] = useState(""), [busy, setBusy] = useState(false), [showPassword, setShowPassword] = useState(false);
  function choose(next: "email" | "phone") { setMethod(next); setMessage(""); setPassword(""); setCode(""); setStep("phone"); }
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); setMessage("");
    if (register && method === "email" && password !== confirmation) { setMessage("تکرار رمز عبور یکسان نیست."); return; }
    setBusy(true);
    try {
      const path = method === "email" ? `/api/v1/auth/email/${register ? "register" : "login"}/` : `/api/v1/auth/${step === "phone" ? "request-code" : "verify-code"}/`;
      const response = await apiPost(path, method === "email" ? { email, password, name } : { phone, code, password });
      const json = response.headers.get("content-type")?.includes("application/json");
      if (!json) { setMessage(response.status === 403 ? "نشست امن تأیید نشد. صفحه را تازه کن؛ در نسخهٔ عملیاتی اتصال HTTPS لازم است." : "پاسخ سرویس ورود قابل پردازش نیست. دوباره تلاش کن."); return; }
      const result = await response.json();
      if (!response.ok) { setMessage(errors[result.error] ?? "درخواست انجام نشد. اطلاعات را بررسی کن."); return; }
      if (method === "phone" && step === "phone") { setStep("code"); setMessage("کد ورود ارسال شد."); }
      else { router.push("/account/"); router.refresh(); }
    } catch { setMessage("ارتباط با سرویس ورود برقرار نشد. اتصال را بررسی کن و دوباره تلاش کن."); }
    finally { setBusy(false); }
  }
  return <main className="gz-auth-page"><section className="gz-auth-story"><span className="gz-kicker">همهٔ انتخاب‌هایت، در یک جا</span><h2>خوش آمدی به<br /><span>انتخاب‌های روشن‌تر.</span></h2><p>با حساب گزیناو، علاقه‌مندی‌هایت را نگه دار، سفارش‌ها را دنبال کن و از انتخاب‌هایت جلوتر بمان.</p><BrandMark className="gz-auth-mark" /><ul><li><UiIcon name="check" />مقایسهٔ پیشنهاد فروشندگان</li><li><UiIcon name="check" />پیگیری یکپارچهٔ سفارش‌ها</li><li><UiIcon name="check" />دسترسی با ایمیل یا موبایل</li></ul><small>GOZINAV / انتخاب، به سبک تو.</small></section><section className="gz-auth-card"><Brand /><h1>{register && method === "email" ? "حساب خودت را بساز." : "خوش برگشتی."}</h1><p>با روشی که راحت‌تری ادامه بده.</p><div className="gz-auth-methods" role="group" aria-label="روش ورود"><button type="button" disabled={busy} aria-pressed={method === "email"} onClick={() => choose("email")}>ایمیل و رمز عبور</button><button type="button" disabled={busy} aria-pressed={method === "phone"} onClick={() => choose("phone")}>موبایل و کد تأیید</button></div><form onSubmit={submit} aria-label={register ? "ثبت‌نام با ایمیل" : "ورود به حساب"}>
    {method === "email" ? <>{register && <label htmlFor="name">نام<input id="name" value={name} onChange={e => setName(e.target.value)} autoComplete="given-name" maxLength={150} required /></label>}<label htmlFor="email">ایمیل<input id="email" type="email" dir="ltr" value={email} onChange={e => setEmail(e.target.value)} autoComplete="email" maxLength={254} placeholder="you@example.com" required /></label><label htmlFor="password">رمز عبور<span className="gz-password-field"><input id="password" type={showPassword ? "text" : "password"} dir="ltr" value={password} onChange={e => setPassword(e.target.value)} autoComplete={register ? "new-password" : "current-password"} minLength={register ? 10 : 1} maxLength={128} required /><button type="button" className="gz-password-toggle" aria-label={showPassword ? "پنهان‌کردن رمز عبور" : "نمایش رمز عبور"} onClick={() => setShowPassword(!showPassword)}>{showPassword ? "پنهان" : "نمایش"}</button></span></label>{register && <><small>حداقل ۱۰ نویسه؛ ترکیبی غیررایج و متفاوت از نام و ایمیلت انتخاب کن.</small><label htmlFor="confirmation">تکرار رمز عبور<input id="confirmation" type={showPassword ? "text" : "password"} dir="ltr" autoComplete="new-password" value={confirmation} onChange={e => setConfirmation(e.target.value)} maxLength={128} required /></label></>}</> : <><label htmlFor="phone">شمارهٔ موبایل<input id="phone" type="tel" dir="ltr" value={phone} onChange={e => setPhone(e.target.value)} autoComplete="tel" placeholder="09123456789" disabled={step === "code"} maxLength={16} required /></label>{step === "code" && <><label htmlFor="code">کد شش‌رقمی<input id="code" dir="ltr" inputMode="numeric" autoComplete="one-time-code" maxLength={6} minLength={6} value={code} onChange={e => setCode(e.target.value)} required /></label><label htmlFor="staff-password">رمز کارکنان (فقط برای کارکنان)<input id="staff-password" type="password" value={password} onChange={e => setPassword(e.target.value)} autoComplete="current-password" maxLength={128} /></label><button className="gz-text-button" type="button" onClick={() => {setStep("phone");setCode("");setMessage("");}}>ویرایش شماره / درخواست کد تازه</button></>}</>}
    {message && <p role="status" className="gz-form-message">{message}</p>}<button className="gz-button gz-auth-submit" type="submit" disabled={busy}>{busy ? "در حال بررسی…" : method === "phone" ? step === "phone" ? "دریافت کد تأیید" : "تأیید و ورود" : register ? "ساخت حساب" : "ورود به حساب"}<UiIcon name="arrow" /></button></form>{method === "email" && <p className="gz-auth-switch">{register ? "حساب داری؟" : "هنوز حساب نداری؟"} <button type="button" disabled={busy} onClick={() => {setRegister(!register);setMessage("");setPassword("");setConfirmation("");}}>{register ? "وارد شو" : "حساب بساز"}</button></p>}<a className="gz-auth-help" href="/support/">برای ورود به راهنمایی نیاز داری؟</a></section></main>;
}