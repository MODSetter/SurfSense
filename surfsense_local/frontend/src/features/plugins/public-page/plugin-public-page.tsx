import { useId } from "react"

import { Button } from "@/components/ui/button"
import { ArrowLeftIcon } from "@/components/ui/icons"
import { intl } from "@/i18n/intl"

import { ConnectListedPlugin } from "../browse/connect-listed-plugin"
import { PluginIcon } from "../plugin-icon"
import { isRegistryEntry, type ListedEntry } from "./listed-entry"
import { ListedTools } from "./listed-tools"
import { PageSection } from "./page-section"
import { PluginFacts } from "./plugin-facts"
import { PublisherByline } from "./publisher-byline"

/**
 * A listed plugin's public page, opened from Browse: built from its list entry alone,
 * so the same for every user and whether it is connected or not. Its settings are in Yours.
 */
export function PluginPublicPage({
  entry,
  onBack,
}: {
  entry: ListedEntry
  onBack: () => void
}) {
  const nameId = useId()
  return (
    <div className="flex flex-col gap-3">
      <Button
        type="button"
        variant="ghost"
        size="sm"
        className="-ml-2 self-start text-muted-foreground"
        onClick={onBack}
      >
        <ArrowLeftIcon data-icon="inline-start" />
        {intl.formatMessage({
          id: "plugins_page_back_button",
          defaultMessage: "Back",
        })}
      </Button>
      <section aria-labelledby={nameId}>
        <div className="flex items-start justify-between gap-6">
          <div className="flex min-w-0 items-center gap-3">
            <PluginIcon
              id={entry.id}
              name={entry.name}
              hasIcon={entry.has_icon}
              firstParty={!isRegistryEntry(entry)}
            />
            <div className="min-w-0">
              <h3 id={nameId} className="truncate text-base font-medium">
                {entry.name}
              </h3>
              <p className="flex text-xs text-muted-foreground">
                <PublisherByline entry={entry} />
              </p>
            </div>
          </div>
          <ConnectListedPlugin entry={entry} />
        </div>
        <PageSection
          title={intl.formatMessage({
            id: "plugins_page_about_title",
            defaultMessage: "About",
          })}
        >
          <p className="text-sm text-muted-foreground">
            {entry.about ?? entry.description}
          </p>
        </PageSection>
        <PageSection
          title={intl.formatMessage({
            id: "plugins_page_tools_title",
            defaultMessage: "Tools",
          })}
        >
          <ListedTools tools={entry.tools} />
        </PageSection>
        <PageSection
          title={intl.formatMessage({
            id: "plugins_page_details_title",
            defaultMessage: "Details",
          })}
        >
          <PluginFacts entry={entry} />
        </PageSection>
      </section>
    </div>
  )
}
