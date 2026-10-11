export const siteUrl = (process.env.SITE_URL ?? "http://localhost:5067").replace(/\/$/, "");
export const internalApi = process.env.API_INTERNAL_URL ?? "http://localhost:8000";

// Internal server requests must mark TLS terminated at the isolated edge.
export const internalHeaders: Record<string, string> = process.env.API_INTERNAL_TLS === "1" ? { "X-Forwarded-Proto": "https" } : {};
