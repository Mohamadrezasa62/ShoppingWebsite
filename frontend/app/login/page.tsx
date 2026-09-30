"use client";

import { FormEvent, useState } from "react";
import { useRouter } from "next/navigation";
import { apiPost } from "@/lib/api";

export default function LoginPage() {
  const router = useRouter();
  const [phone, setPhone] = useState("");
  const [code, setCode] = useState("");
  const [step, setStep] = useState<"phone" | "code">("phone");
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    setMessage("");
    try {
      const response = step === "phone"
        ? await apiPost("/api/v1/auth/request-code/", { phone })
        : await apiPost("/api/v1/auth/verify-code/", { phone, code });
      if (!response.ok) {
        setMessage(response.status === 429 ? "کمی بعد دوباره تلاش کنید." : "درخواست انجام نشد. اطلاعات را بررسی کنید.");
      } else if (step === "phone") {
        setStep("code");
        setMessage("کد ورود ارسال شد.");
      } else {
        router.push("/account");
      }
    } catch {
      setMessage("ارتباط با سرور برقرار نشد.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="form-page">
      <form className="form-card" onSubmit={submit}>
        <a href="/" className="brand">ShoppingWebsite</a>
        <h1>ورود یا ثبت‌نام</h1>
        <p>برای ادامه شمارهٔ موبایل خود را وارد کنید.</p>
        <label htmlFor="phone">شمارهٔ موبایل</label>
        <input id="phone" name="phone" type="tel" inputMode="tel" autoComplete="tel" required value={phone} onChange={(event) => setPhone(event.target.value)} disabled={step === "code"} placeholder="۰۹۱۲۳۴۵۶۷۸۹" />
        {step === "code" && <>
          <label htmlFor="code">کد شش‌رقمی</label>
          <input id="code" name="code" inputMode="numeric" autoComplete="one-time-code" maxLength={6} required value={code} onChange={(event) => setCode(event.target.value)} />
        </>}
        <button disabled={busy} type="submit">{step === "phone" ? "دریافت کد" : "تأیید و ورود"}</button>
        {message && <p role="status">{message}</p>}
      </form>
    </main>
  );
}
