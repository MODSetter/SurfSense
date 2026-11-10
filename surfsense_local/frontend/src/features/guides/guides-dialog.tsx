import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { ExternalLink } from "@/features/about/external-link"
import { useAppDetails } from "@/features/about/use-app-details"
import { intl } from "@/i18n/intl"

import { GUIDE_AREAS } from "./guide-catalog"
import { guidesUrl, guideUrl } from "./guide-links"

// utm_content for every link here.
const SURFACE = "guides_dialog"

/**
 * The guides on surfsense.com by area, each opening in the browser. Nothing is
 * bundled or fetched: installers have size budgets, the screenshots are English,
 * and the app fetches no media on its own.
 */
export function GuidesDialog({
  open,
  onOpenChange,
}: {
  open: boolean
  onOpenChange: (open: boolean) => void
}) {
  const version = useAppDetails().data?.version
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-h-[calc(100dvh-2rem)] overflow-y-auto select-none sm:max-w-lg">
        <DialogHeader>
          <DialogTitle>
            {intl.formatMessage({
              id: "guides_dialog_title",
              defaultMessage: "Guides and videos",
            })}
          </DialogTitle>
          <DialogDescription className="text-pretty">
            {intl.formatMessage({
              id: "guides_dialog_body",
              defaultMessage:
                "Step-by-step guides with short videos, on surfsense.com. Each opens in your browser, and is in English.",
            })}
          </DialogDescription>
        </DialogHeader>
        <div className="flex flex-col gap-5">
          {GUIDE_AREAS.map((area) => (
            <section
              key={area.key}
              aria-labelledby={`guides-${area.key}`}
              className="flex flex-col gap-2"
            >
              <h3 id={`guides-${area.key}`} className="text-sm font-medium">
                {area.title()}
              </h3>
              <ul className="flex flex-col gap-1.5">
                {area.guides.map((guide) => (
                  <li key={guide.slug}>
                    <ExternalLink href={guideUrl(guide.slug, SURFACE, version)}>
                      {guide.title()}
                    </ExternalLink>
                  </li>
                ))}
              </ul>
            </section>
          ))}
        </div>
        <DialogFooter>
          <ExternalLink href={guidesUrl(SURFACE, version)}>
            {intl.formatMessage({
              id: "guides_dialog_all_link",
              defaultMessage: "All guides on surfsense.com",
            })}
          </ExternalLink>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
