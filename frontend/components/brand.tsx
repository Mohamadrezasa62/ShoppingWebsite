export function BrandMark({ className = "" }: { className?: string }) {
  return <svg className={className} viewBox="0 0 80 80" fill="none" aria-hidden="true"><rect width="80" height="80" rx="23" fill="currentColor" /><path d="M54 23H36a18 18 0 1 0 14 30H37V43h28v18" stroke="var(--on-primary, white)" strokeWidth="8" strokeLinecap="round" strokeLinejoin="round" /></svg>;
}
export function Brand({ compact = false }: { compact?: boolean }) {
  return <a className="gz-brand" href="/" aria-label="گزیناو، صفحهٔ اصلی"><BrandMark />{!compact && <span>گزیناو<small>GOZINAV</small></span>}</a>;
}
