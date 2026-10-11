export function paymentDestination(provider: string, value: string, origin: string): string | null {
  try {
    const target = new URL(value, origin);
    if (target.username || target.password || target.hash) return null;
    if (provider === "zarinpal" && target.origin === "https://payment.zarinpal.com" && /^\/pg\/StartPay\/[A-Za-z0-9]{20,160}$/.test(target.pathname) && !target.search) return target.href;
    if (provider === "sandbox" && target.origin === origin && target.pathname === "/sandbox-payment/" && /^\?attempt=\d+$/.test(target.search)) return target.href;
  } catch { return null; }
  return null;
}
