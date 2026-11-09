/**
 * The announcement switches. NEXT_PUBLIC_* values are baked in at `next build`,
 * so a change needs a redeploy.
 */

// Global announcement banner at the top of every page. Toggle on Vercel via
// NEXT_PUBLIC_GLOBAL_ANNOUNCEMENT_ENABLED ("true" to show), set the copy with
// NEXT_PUBLIC_GLOBAL_ANNOUNCEMENT_MESSAGE, and the colour with
// NEXT_PUBLIC_GLOBAL_ANNOUNCEMENT_TONE: "info" (default) or "warning".
export const GLOBAL_ANNOUNCEMENT_ENABLED =
	process.env.NEXT_PUBLIC_GLOBAL_ANNOUNCEMENT_ENABLED === "true";

export const GLOBAL_ANNOUNCEMENT_MESSAGE =
	process.env.NEXT_PUBLIC_GLOBAL_ANNOUNCEMENT_MESSAGE ?? "";

export const GLOBAL_ANNOUNCEMENT_TONE: "info" | "warning" =
	process.env.NEXT_PUBLIC_GLOBAL_ANNOUNCEMENT_TONE === "warning" ? "warning" : "info";

// The announcement pill above the homepage headline, distinct from the banner
// above. Toggle via NEXT_PUBLIC_TOP_ANNOUNCEMENT_ENABLED ("true" to show); the
// name predates the pill, kept so deployments keep working. The copy and link
// are fixed in HomeAnnouncement.
export const TOP_ANNOUNCEMENT_ENABLED = process.env.NEXT_PUBLIC_TOP_ANNOUNCEMENT_ENABLED === "true";
