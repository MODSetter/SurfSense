import type { ComponentType } from "react"

import { Button } from "@/components/ui/button"
import { DownloadCircle02Icon, LicenseIcon } from "@/components/ui/icons"
import { askEgress } from "@/features/egress/egress-prompt"
import { useLicense } from "@/features/license/use-license"
import {
  updatesBridge,
  useUpdatePrefs,
  useUpdateState,
} from "@/features/updates/use-update-state"
import type { UpdateState } from "@/lib/api"
import { cn } from "@/lib/utils"

const TONE = {
  quiet: "text-muted-foreground",
  offer: "text-notice hover:text-notice",
  wrong: "text-amber-600 dark:text-amber-500",
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

// `active` has no row: a working license is not news. Nor is "none" a warning
// -- the app is free and only paid plugins need a file, so a user who never
// bought one gets an invitation in the quiet tone, not an alert.
const LICENSE_ROWS: Record<
  "none" | "license_expired" | "clock_untrusted",
  Row
> = {
  none: { label: "Unlock plugins", tone: "quiet" },
  license_expired: { label: "License expired", tone: "wrong" },
  clock_untrusted: { label: "Clock is off", tone: "wrong" },
}

function updateRow(state: UpdateState): Row {
  switch (state.status) {
    case "checking":
      return { label: "Checking…", tone: "quiet", busy: true }
    case "downloading":
      return { label: "Downloading…", tone: "quiet", busy: true }
    case "ready":
      return { label: "Restart to update", tone: "offer" }
    case "up-to-date":
      return { label: "Up to date", tone: "quiet" }
    case "error":
      return { label: "Update check failed", tone: "wrong" }
    default:
      return { label: "Check for updates", tone: "quiet" }
  }
}

/**
 * The sidebar's bottom edge, holding only what is worth a glance: a license
 * that needs attention, and where the app stands on updates.
 *
 * Either row can be absent -- no bridge outside the desktop app, no license row
 * once one is active -- so the strip goes with them rather than leaving a
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

  const licenseRow =
    license && license.state !== "active" ? LICENSE_ROWS[license.state] : null

  if (!licenseRow && !updates) return null

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
      {licenseRow ? (
        <FooterRow
          icon={LicenseIcon}
          row={licenseRow}
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
