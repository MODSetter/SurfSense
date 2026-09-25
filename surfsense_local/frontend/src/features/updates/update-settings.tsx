import { Button } from "@/components/ui/button"
import { DownloadCircle02Icon } from "@/components/ui/icons"
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip"
import { askEgress } from "@/features/egress/ask-egress"
import { intl } from "@/i18n/intl"
import type { UpdateState } from "@/lib/api"

import {
  updatesBridge,
  useUpdatePrefs,
  useUpdateState,
} from "./use-update-state"

export type { UpdateState }

function statusText(state: UpdateState) {
  switch (state.status) {
    case "checking":
      return intl.formatMessage({
        id: "updates_settings_checking_status",
        defaultMessage: "Checking…",
      })
    case "up-to-date":
      return intl.formatMessage({
        id: "updates_settings_up_to_date_status",
        defaultMessage: "SurfSense is up to date",
      })
    case "downloading":
      return intl.formatMessage(
        {
          id: "updates_settings_downloading_status",
          defaultMessage: "Downloading {version}…",
        },
        {
          version: state.version,
        }
      )
    case "ready":
      return intl.formatMessage(
        {
          id: "updates_settings_ready_status",
          defaultMessage: "SurfSense {version} is ready to install",
        },
        { version: state.version }
      )
    default:
      return null
  }
}

export function UpdateSettings() {
  const updates = updatesBridge()
  const state = useUpdateState()
  const { prefs, setAutomatic } = useUpdatePrefs()

  if (!updates || prefs === null) return null

  // Installing is local and needs no permission. Checking asks github.com, and
  // Settings > Network promises that call is refused until allowed -- so the
  // first check asks, the same way the sidebar's does.
  const onCheckClick = async () => {
    if (prefs.automatic) return void updates.check()
    const allowed = await askEgress({
      destination: "app_updates",
      host: "github.com",
      allow: () => setAutomatic(true),
    })
    if (allowed) await updates.check()
  }

  const text = statusText(state)
  return (
    <div className="mt-8 flex items-start justify-between gap-8">
      <div className="flex flex-col gap-1">
        <h3 className="text-sm font-medium">
          {intl.formatMessage({
            id: "updates_settings_title",
            defaultMessage: "App updates",
          })}
        </h3>
        <p className="text-sm text-pretty text-muted-foreground">
          {intl.formatMessage({
            id: "updates_settings_body",
            defaultMessage:
              "Free updates from GitHub Releases. SurfSense stays silent until you allow App updates under Network, which also enables the launch check.",
          })}
        </p>
        {state.status === "error" ? (
          <p role="alert" className="text-sm text-destructive">
            {intl.formatMessage(
              {
                id: "updates_settings_check_error",
                defaultMessage: "Could not check for updates: {message}",
              },
              { message: state.message }
            )}
          </p>
        ) : text ? (
          <p className="text-sm text-muted-foreground">{text}</p>
        ) : null}
      </div>
      {state.status === "ready" ? (
        <Button type="button" onClick={() => void updates.install()}>
          {intl.formatMessage({
            id: "updates_settings_restart_button",
            defaultMessage: "Restart to update",
          })}
        </Button>
      ) : (
        <Button
          type="button"
          variant="outline"
          disabled={
            state.status === "checking" || state.status === "downloading"
          }
          onClick={() => void onCheckClick()}
        >
          {intl.formatMessage({
            id: "updates_settings_check_button",
            defaultMessage: "Check now",
          })}
        </Button>
      )}
    </div>
  )
}

/**
 * Sits in the title bar and appears only once an update has been downloaded
 * and is waiting. Shaped exactly like the right-panel toggle beside it — ghost,
 * same size — so only the color sets it apart.
 *
 * The title bar is `position: fixed`, so this button is out of the document
 * flow: rendering nothing costs no space and cannot disturb the layout around
 * it.
 */
export function UpdateButton() {
  const state = useUpdateState()
  if (state.status !== "ready") return null
  const label = intl.formatMessage(
    {
      id: "updates_title_bar_restart_tooltip",
      defaultMessage: "Restart to install {version}",
    },
    {
      version: state.version,
    }
  )
  return (
    <Tooltip>
      <TooltipTrigger
        render={
          <Button
            type="button"
            variant="ghost"
            size="icon-sm"
            aria-label={label}
            className="pointer-events-auto size-6 text-notice hover:text-notice"
            onClick={() => void updatesBridge()?.install()}
          >
            <DownloadCircle02Icon />
          </Button>
        }
      />
      <TooltipContent side="bottom" collisionPadding={8}>
        {label}
      </TooltipContent>
    </Tooltip>
  )
}
