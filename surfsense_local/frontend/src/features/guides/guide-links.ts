import { siteVisitUrl } from "@/features/external-links/site-visit-url"

// The step-by-step guides on surfsense.com. Each must pass
// electron/src/main/external-url.ts, which lets any surfsense.com page through.
const GUIDES_URL = "https://www.surfsense.com/docs/v2/guides"

/** A guide's address on surfsense.com, after /docs/v2/guides/. */
export type GuideSlug =
  | "set-up"
  | "local-model"
  | "connect-a-server"
  | "add-sources"
  | "ask-and-cite"
  | "pick-sources"
  | "add-from-the-web"
  | "organise-sources"
  | "workspaces"
  | "studio-documents"
  | "study-materials"
  | "podcast"
  | "refine-and-versions"
  | "images"
  | "agent-documents"
  | "tracked-changes"
  | "analyse-a-spreadsheet"
  | "pdf-tools"
  | "web-research"
  | "plugins"
  | "transcribe-a-recording"
  | "voice-input"
  | "business-trial"
  | "security-questionnaire"
  | "contract-redline"
  | "privacy-network"
  | "updates"

/** Every guide, tagged with the place in the app it was opened from. */
export function guidesUrl(
  surface: string,
  version: string | undefined
): string {
  return siteVisitUrl(GUIDES_URL, surface, version)
}

export function guideUrl(
  slug: GuideSlug,
  surface: string,
  version: string | undefined
): string {
  return siteVisitUrl(`${GUIDES_URL}/${slug}`, surface, version)
}
