"use client";

import { useEffect, useState } from "react";

export function PortalAccess({ title, endpoint }: { title: string; endpoint: string }) {
  const [state, setState] = useState<"loading" | "allowed" | "denied">("loading");

  useEffect(() => {
    fetch(endpoint, { credentials: "same-origin" })
      .then((response) => setState(response.ok ? "allowed" : "denied"))
      .catch(() => setState("denied"));
  }, [endpoint]);

  return <main className="form-page"><section className="form-card">
    <a href="/account" className="brand">گزیناو</a>
    <h1>{title}</h1>
    {state === "loading" && <p>در حال بررسی دسترسی...</p>}
    {state === "denied" && <p>دسترسی به این بخش برای حساب شما فعال نیست.</p>}
    {state === "allowed" && <p>دسترسی تأیید شد. ابزارهای این پنل در مراحل بعدی اضافه می‌شوند.</p>}
  </section></main>;
}
