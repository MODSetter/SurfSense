import type { ComponentType } from "react"

import { Button } from "@/components/ui/button"
import { LicenseIcon } from "@/components/ui/icons"
import type { LicenseState } from "@/features/license/api"
import { useLicense } from "@/features/license/use-license"
import { intl } from "@/i18n/intl"
import { cn } from "@/lib/utils"

// `good` and `bad` keep their colour on hover, where ghost would otherwise
// repaint them: a status light that changes colour under the pointer is no
// longer reporting anything.
const TONE = {
  good: "text-emerald-600 hover:text-emerald-600 dark:text-emerald-500 dark:hover:text-emerald-500",
  bad: "text-destructive hover:text-destructive",
} as const

type Row = {
  label: string
  tone: keyof typeof TONE
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
      static
      type="button"
      variant="ghost"
      size="xs"
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

/**
 * The sidebar's bottom edge: where the license stands, at a glance. Updates
 * show in the title bar instead.
 *
 * Absent until the license status arrives, so the strip never leaves a
 * bordered gap.
 */
export function SidebarFooter({
  onOpenLicense,
}: {
  onOpenLicense: () => void
}) {
  const license = useLicense().data
  if (!license) return null

  return (
    <div className="flex flex-col gap-0.5 border-t p-2">
      <FooterRow
        icon={LicenseIcon}
        row={licenseRow(license.state)}
        onClick={onOpenLicense}
      />
    </div>
  )
}
