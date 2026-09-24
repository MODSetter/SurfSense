import type { ComponentType } from "react"

import { Button } from "@/components/ui/button"
import { DownloadCircle02Icon, LicenseIcon } from "@/components/ui/icons"
import { askEgress } from "@/features/egress/ask-egress"
import type { LicenseState } from "@/features/license/api"
import { useLicense } from "@/features/license/use-license"
import {
  updatesBridge,
  useUpdatePrefs,
  useUpdateState,
} from "@/features/updates/use-update-state"
import { intl } from "@/i18n/intl"
import type { UpdateState } from "@/lib/api"
import { cn } from "@/lib/utils"

// `good` and `bad` keep their colour on hover, where ghost would otherwise
// repaint them: a status light that changes colour under the pointer is no
// longer reporting anything.
const TONE = {
  quiet: "text-muted-foreground",
  offer: "text-notice hover:text-notice",
  wrong: "text-amber-600 dark:text-amber-500",
  good: "text-emerald-600 hover:text-emerald-600 dark:text-emerald-500 dark:hover:text-emerald-500",
  bad: "text-destructive hover:text-destructive",
} as const

type Row = {
  label: string
  tone: keyof typeof TONE
  busy?: boolean
}

function FooterRow({
  icon: Icon,
  row,
  onClick,
}: {
  icon: ComponentType<{ className?: string }>
  row: Row
  onClick: () => void
}) {
  return (
    <Button
      type="button"
      variant="ghost"
      size="xs"
      disabled={row.busy}
      className={cn("w-full justify-start px-2 font-normal", TONE[row.tone])}
      onClick={onClick}
    >
      <Icon />
      <span className="truncate">{row.label}</span>
    </Button>
  )
}

// The row answers "is my license working?" at a glance, so it reads as a status
// light: green only when plugins are actually unlocked, red for every state
// that leaves them locked, whatever the reason.
const LICENSE_ROWS: Record<
  LicenseState,
  { label: () => string; tone: Row["tone"] }
> = {
  active: {
    label: () =>
      intl.formatMessage({
        id: "dashboard_footer_license_active_status",
        defaultMessage: "License active",
      }),
    tone: "good",
  },
  none: {
    label: () =>
      intl.formatMessage({
        id: "dashboard_footer_license_none_status",
        defaultMessage: "No license",
      }),
    tone: "bad",
  },
  license_expired: {
    label: () =>
      intl.formatMessage({
        id: "dashboard_footer_license_expired_status",
        defaultMessage: "License expired",
      }),
    tone: "bad",
  },
  clock_untrusted: {
    label: () =>
      intl.formatMessage({
        id: "dashboard_footer_license_clock_status",
        defaultMessage: "Clock is off",
      }),
    tone: "bad",
  },
}

function licenseRow(state: LicenseState): Row {
  // A state this build does not know reads as locked, not as a crash of the
  // whole dashboard.
  const { label, tone } = LICENSE_ROWS[state] ?? LICENSE_ROWS.none
  return { label: label(), tone }
}

function updateRow(state: UpdateState): Row {
  switch (state.status) {
    case "checking":
      return {
        label: intl.formatMessage({
          id: "dashboard_footer_update_checking_status",
          defaultMessage: "Checking…",
        }),
        tone: "quiet",
        busy: true,
      }
    case "downloading":
      return {
        label: intl.formatMessage({
          id: "dashboard_footer_update_downloading_status",
          defaultMessage: "Downloading…",
        }),
        tone: "quiet",
        busy: true,
      }
    case "ready":
      return {
        label: intl.formatMessage({
          id: "dashboard_footer_update_restart_button",
          defaultMessage: "Restart to update",
        }),
        tone: "offer",
      }
    case "up-to-date":
      return {
        label: intl.formatMessage({
          id: "dashboard_footer_update_current_status",
          defaultMessage: "Up to date",
        }),
        tone: "quiet",
      }
    case "error":
      return {
        label: intl.formatMessage({
          id: "dashboard_footer_update_failed_status",
          defaultMessage: "Update check failed",
        }),
        tone: "wrong",
      }
    default:
      return {
        label: intl.formatMessage({
          id: "dashboard_footer_update_check_button",
          defaultMessage: "Check for updates",
        }),
        tone: "quiet",
      }
  }
}

/**
 * The sidebar's bottom edge, holding only what is worth a glance: where the
 * license stands, and where the app stands on updates.
 *
 * Either row can be absent -- no bridge outside the desktop app, no license row
 * until its status arrives -- so the strip goes with them rather than leaving a
 * bordered gap.
 */
export function SidebarFooter({
  onOpenLicense,
}: {
  onOpenLicense: () => void
}) {
  const license = useLicense().data
  const updates = updatesBridge()
  const state = useUpdateState()
  const { prefs, setAutomatic } = useUpdatePrefs()

  const currentLicenseRow = license ? licenseRow(license.state) : null

  if (!currentLicenseRow && !updates) return null

  // Installing is local and needs no permission. Checking asks github.com, and
  // Settings > Network promises that call is refused until allowed -- so the
  // first one asks, the same way picking a remote model does.
  const onUpdateClick = async () => {
    if (!updates) return
    if (state.status === "ready") return void updates.install()
    if (prefs?.automatic) return void updates.check()
    const allowed = await askEgress({
      destination: "app_updates",
      host: "github.com",
      allow: () => setAutomatic(true),
    })
    if (allowed) await updates.check()
  }

  return (
    <div className="flex flex-col gap-0.5 border-t p-2">
      {currentLicenseRow ? (
        <FooterRow
          icon={LicenseIcon}
          row={currentLicenseRow}
          onClick={onOpenLicense}
        />
      ) : null}
      {updates ? (
        <FooterRow
          icon={DownloadCircle02Icon}
          row={updateRow(state)}
          onClick={() => void onUpdateClick()}
        />
      ) : null}
    </div>
  )
}
