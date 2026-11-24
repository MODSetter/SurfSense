// The sites SurfSense reads more than the page from: product names, not translated.
const PULLER_NAMES: Record<string, string> = {
  youtube: "YouTube",
}

/** Null for a page read as it is: nothing to say beyond its site. */
export function pullerName(puller: string): string | null {
  return PULLER_NAMES[puller] ?? null
}
