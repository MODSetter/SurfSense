import { useId, useState } from "react"

import { Button } from "@/components/ui/button"
import { ChevronRightIcon } from "@/components/ui/icons"
import type { LocalBuild } from "@/features/models/local/chat/api"
import { ModelSearch } from "@/features/models/local/chat/model-search"
import type { InstallState } from "@/features/models/local/create-install"
import { intl } from "@/i18n/intl"
import { cn } from "@/lib/utils"

/**
 * Settings' Hugging Face search, one line until asked for. Closed by default:
 * what is typed goes to a third party and raises the egress question, and the
 * tested list above is enough for most people.
 */
export function HuggingFaceSearch({
  installState,
  disabled,
  onInstall,
  onCancel,
}: {
  installState: InstallState
  disabled: boolean
  onInstall: (build: LocalBuild, label: string) => void
  onCancel: () => void
}) {
  const searchId = useId()
  const [open, setOpen] = useState(false)

  return (
    <div className="flex flex-col gap-3">
      <Button
        type="button"
        variant="ghost"
        size="sm"
        className="self-start text-muted-foreground"
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
      {open ? (
        <div id={searchId}>
          <ModelSearch
            autoFocus
            onInstall={onInstall}
            onCancel={onCancel}
            installState={installState}
            disabled={disabled}
          />
        </div>
      ) : null}
    </div>
  )
}
