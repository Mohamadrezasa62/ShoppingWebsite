export function csrfToken(): string | undefined {
  if (typeof document === "undefined") return undefined;
  return document.cookie
    .split("; ")
    .find((cookie) => cookie.startsWith("csrftoken="))
    ?.split("=")[1];
}

export async function apiPost(path: string, body: Record<string, string>) {
  await fetch("/api/v1/auth/csrf/", { credentials: "same-origin" });
  return fetch(path, {
    method: "POST",
    headers: { "Content-Type": "application/json", "X-CSRFToken": csrfToken() ?? "" },
    credentials: "same-origin",
    body: JSON.stringify(body),
  });
}
