const paths = {
  home: "m3 10 9-7 9 7v10H3V10Zm6 10v-7h6v7",
  grid: "M3 3h7v7H3V3Zm11 0h7v7h-7V3ZM3 14h7v7H3v-7Zm11 0h7v7h-7v-7Z",
  search: "M20 20l-5-5M17 10a7 7 0 1 1-14 0 7 7 0 0 1 14 0Z",
  heart: "M20.5 4.5a5 5 0 0 0-7 0L12 6l-1.5-1.5a5 5 0 0 0-7 7L12 20l8.5-8.5a5 5 0 0 0 0-7Z",
  bag: "M4 8h16l1 13H3L4 8Zm4 0V6a4 4 0 0 1 8 0v2",
  user: "M20 21v-2a8 8 0 0 0-16 0v2M16 7a4 4 0 1 1-8 0 4 4 0 0 1 8 0Z",
  box: "m3 7 9-4 9 4-9 4-9-4Zm0 0v10l9 4 9-4V7M12 11v10",
  support: "M3 14v-3a9 9 0 0 1 18 0v3M3 12h4v7H3v-7Zm14 0h4v7h-4v-7Zm4 7c0 3-5 3-8 3",
  compare: "M8 3v18M16 3v18M4 7h8M12 17h8M4 17h4M16 7h4",
  bell: "M18 8a6 6 0 0 0-12 0c0 7-3 7-3 9h18c0-2-3-2-3-9M10 21h4",
  menu: "M4 6h16M4 12h16M4 18h16", arrow: "M20 12H4m6-6-6 6 6 6", check: "m5 12 4 4L19 6",
  book: "M12 5c-4-3-7-2-10-1v15c3-1 6-2 10 1 4-3 7-2 10-1V4c-3-1-6-2-10 1Zm0 0v15", close: "m5 5 14 14M19 5 5 19",
} as const;
export type IconName = keyof typeof paths;
export function UiIcon({ name, className = "" }: { name: IconName; className?: string }) {
  return <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.65" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d={paths[name]} /></svg>;
}
