// The sites a plugin adds more than the page from: product names, not translated.
const PULLER_NAMES: Record<string, string> = {
  youtube: "YouTube",
  tiktok: "TikTok",
  google_maps: "Google Maps",
  amazon: "Amazon",
  walmart: "Walmart",
  indeed: "Indeed",
  reddit: "Reddit",
  instagram: "Instagram",
}

/** Null for a page Web Crawl reads: nothing to say beyond its site. */
export function pullerName(puller: string): string | null {
  return PULLER_NAMES[puller] ?? null
}
