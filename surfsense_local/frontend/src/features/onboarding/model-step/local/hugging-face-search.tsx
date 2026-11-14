import { useId, useState, type ReactNode } from "react"

import { Button } from "@/components/ui/button"
import { ChevronRightIcon } from "@/components/ui/icons"
import type { LocalBuild } from "@/features/models/local/chat/api"
import { ModelSearch } from "@/features/models/local/chat/model-search"
import type { SearchSource } from "@/features/models/local/chat/search-source"
import type { InstallJob } from "@/features/models/local/installs/api"
import { intl } from "@/i18n/intl"
import { cn } from "@/lib/utils"

/**
 * Settings' Hugging Face search, one line until asked for. Closed by default:
 * what is typed goes to a third party and raises the egress question, and the
 * tested list above is enough for most people.
 */
export function HuggingFaceSearch({
  jobs,
  disabled,
  onInstall,
  onCancel,
  source,
  note,
  aside,
}: {
  jobs: readonly InstallJob[]
  disabled: boolean
  onInstall: (build: LocalBuild) => void
  onCancel: (jobId: string) => void
  /** GGUF unless a step searches another engine's models. */
  source?: SearchSource
  note?: string
  /** Sits at the other end of the search's line, for what shares its row. */
  aside?: ReactNode
}) {
  const searchId = useId()
  const [open, setOpen] = useState(false)

  return (
    <div className="flex flex-col gap-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <Button
          type="button"
          variant="ghost"
          size="sm"
          className="text-muted-foreground"
          aria-expanded={open}
          aria-controls={searchId}
          onClick={() => setOpen((value) => !value)}
        >
          {open
            ? intl.formatMessage({
                id: "onboarding_hugging_face_search_hide_button",
                defaultMessage: "Hide Hugging Face search",
              })
            : intl.formatMessage({
                id: "onboarding_hugging_face_search_show_button",
                defaultMessage: "Not listed? Search Hugging Face",
              })}
          <ChevronRightIcon
            data-icon="inline-end"
            className={cn(
              "transition-transform motion-reduce:transition-none",
              open && "rotate-90"
            )}
          />
        </Button>
        {aside}
      </div>
      {open ? (
        <div id={searchId}>
          <ModelSearch
            autoFocus
            onInstall={onInstall}
            onCancel={onCancel}
            jobs={jobs}
            disabled={disabled}
            source={source}
            note={note}
          />
        </div>
      ) : null}
    </div>
  )
}
