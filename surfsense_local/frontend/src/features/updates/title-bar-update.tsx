import { useEffect, useRef, useState, type ReactNode } from "react"

import { Button } from "@/components/ui/button"
import { ArrowDown02Icon } from "@/components/ui/icons"
import { Spinner } from "@/components/ui/spinner"
import { intl } from "@/i18n/intl"
import { cn } from "@/lib/utils"

import { DownloadRing } from "./download-ring"
import { updatesBridge, useUpdateState } from "./use-update-state"

// A 20px circle that widens leftwards to show its label on hover or focus.
// interpolate-size lets the width animate to fit the label, whatever its length.
const PILL =
  "group pointer-events-auto flex select-none h-5 w-5 shrink-0 items-center justify-end overflow-hidden rounded-full [interpolate-size:allow-keywords] transition-[width,background-color] duration-150 ease-out hover:w-auto focus-visible:w-auto motion-reduce:transition-none"

// Fades in while sliding out from behind the icon.
const LABEL =
  "translate-x-2 ps-2 pe-0.5 text-[11px] leading-4 font-medium whitespace-nowrap text-notice opacity-0 transition-[opacity,translate] duration-150 ease-out group-hover:translate-x-0 group-hover:opacity-100 group-focus-visible:translate-x-0 group-focus-visible:opacity-100 motion-reduce:translate-x-0 motion-reduce:transition-none"

// Long enough for the quit to begin; if it was cancelled, the pill comes back.
const RESTART_SETTLE_MS = 3000

function Slot({ children }: { children: ReactNode }) {
  return (
    <span className="relative flex size-5 shrink-0 items-center justify-center">
      {children}
    </span>
  )
}

/**
 * Beside the right-panel toggle, the one place updates show outside Settings:
 * a download's progress, then the restart into it. Nothing otherwise, so the
 * title bar keeps no space for it.
 */
export function TitleBarUpdate() {
  const state = useUpdateState()
  const [restarting, setRestarting] = useState(false)
  const settle = useRef<number | undefined>(undefined)
  useEffect(() => () => window.clearTimeout(settle.current), [])

  if (state.status === "downloading") {
    const { percent, version } = state
    return (
      <div
        role="progressbar"
        tabIndex={0}
        aria-label={intl.formatMessage(
          {
            id: "updates_title_bar_downloading_aria",
            defaultMessage: "Downloading SurfSense {version}",
          },
          { version }
        )}
        aria-valuemin={0}
        aria-valuemax={100}
        aria-valuenow={percent ?? undefined}
        className={cn(
          PILL,
          "outline-none hover:bg-notice/10 focus-visible:bg-notice/10 focus-visible:ring-3 focus-visible:ring-ring/50"
        )}
      >
        <span className={LABEL}>
          {percent === null
            ? intl.formatMessage({
                id: "updates_title_bar_downloading_unknown_label",
                defaultMessage: "Downloading…",
              })
            : intl.formatMessage(
                {
                  id: "updates_title_bar_downloading_label",
                  defaultMessage: "Downloading {percent, number, ::percent}",
                },
                { percent: percent / 100 }
              )}
        </span>
        <Slot>
          <DownloadRing percent={percent} className="absolute inset-0" />
          <ArrowDown02Icon className="size-3 text-muted-foreground" />
        </Slot>
      </div>
    )
  }

  if (state.status !== "ready") return null
  const { version } = state
  const restart = () => {
    setRestarting(true)
    void updatesBridge()
      ?.install()
      .finally(() => {
        settle.current = window.setTimeout(
          () => setRestarting(false),
          RESTART_SETTLE_MS
        )
      })
  }
  return (
    <Button
      type="button"
      variant="bare"
      static
      disabled={restarting}
      aria-label={
        restarting
          ? intl.formatMessage(
              {
                id: "updates_title_bar_restarting_aria",
                defaultMessage: "Restarting to install {version}",
              },
              { version }
            )
          : intl.formatMessage(
              {
                id: "updates_title_bar_restart_aria",
                defaultMessage: "Restart to install {version}",
              },
              { version }
            )
      }
      className={cn(
        PILL,
        "bg-notice/20 hover:bg-notice/30 focus-visible:bg-notice/30 disabled:opacity-100"
      )}
      onClick={restart}
    >
      <span className={LABEL}>
        {intl.formatMessage({
          id: "updates_title_bar_ready_label",
          defaultMessage: "Update",
        })}
      </span>
      <Slot>
        {restarting ? (
          <Spinner aria-hidden="true" className="size-3 text-notice" />
        ) : (
          <ArrowDown02Icon className="size-3 text-notice" />
        )}
      </Slot>
    </Button>
  )
}
