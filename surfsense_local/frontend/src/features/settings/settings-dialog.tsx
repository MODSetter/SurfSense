import type { ComponentType } from "react"

import { Button } from "@/components/ui/button"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { CpuIcon, Settings2Icon } from "@/components/ui/icons"
import type { ImportAccepted } from "@/features/migration/api"
import { ImportBundleButton } from "@/features/migration/import-bundle"
import type { ModelSelection } from "@/features/model-selection/api"
import { cn } from "@/lib/utils"

import { AppearanceToggle } from "./appearance-toggle"
import { ModelsSettings } from "./models-settings"
import { SettingsSection } from "./settings-section"

type SettingsNavItem = {
  id: SettingsSectionId
  label: string
  icon: ComponentType<{ className?: string; strokeWidth?: number }>
}

export type SettingsSectionId = "general" | "models"

function GeneralSettings({
  onImported,
}: {
  onImported: (accepted: ImportAccepted) => Promise<void> | void
}) {
  return (
    <SettingsSection
      title="General"
      description="Manage how SurfSense looks and behaves on this device."
    >
      <div className="flex items-center justify-between gap-8">
        <div className="flex flex-col gap-1">
          <h3 className="text-sm font-medium">Appearance</h3>
          <p className="text-sm text-pretty text-muted-foreground">
            Choose how SurfSense looks on this device.
          </p>
        </div>
        <AppearanceToggle />
      </div>
      <div className="mt-8 flex items-center justify-between gap-8">
        <div className="flex flex-col gap-1">
          <h3 className="text-sm font-medium">Import from SurfSense cloud</h3>
          <p className="text-sm text-pretty text-muted-foreground">
            Load the export bundle downloaded from your hosted account.
            Documents arrive as markdown and are indexed in the background;
            original files and live citation links do not travel.
          </p>
        </div>
        <ImportBundleButton onImported={onImported} />
      </div>
    </SettingsSection>
  )
}

// Add future settings pages here; the dialog navigation is generated from this list.
const SETTINGS_SECTIONS = [
  {
    id: "general",
    label: "General",
    icon: Settings2Icon,
  },
  {
    id: "models",
    label: "Models",
    icon: CpuIcon,
  },
] satisfies SettingsNavItem[]

export function SettingsDialog({
  open,
  section,
  onOpenChange,
  onSectionChange,
  onModelUnavailable = () => undefined,
  onModelSelected,
  onImported = () => undefined,
}: {
  open: boolean
  section: SettingsSectionId
  onOpenChange: (open: boolean) => void
  onSectionChange: (section: SettingsSectionId) => void
  onModelUnavailable?: () => void
  onModelSelected: (selection: ModelSelection) => void
  onImported?: (accepted: ImportAccepted) => Promise<void> | void
}) {
  const activeSection =
    SETTINGS_SECTIONS.find((candidate) => candidate.id === section) ??
    SETTINGS_SECTIONS[0]

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="h-[640px] min-h-0 w-[1000px] max-w-none gap-0 overflow-hidden rounded-2xl p-0 shadow-xl select-none sm:max-w-none">
        <DialogHeader className="sr-only">
          <DialogTitle>Settings</DialogTitle>
          <DialogDescription>
            Manage your SurfSense preferences.
          </DialogDescription>
        </DialogHeader>

        <div className="grid h-full min-h-0 grid-cols-[184px_minmax(0,1fr)]">
          <aside className="border-r bg-sidebar p-3 text-sidebar-foreground">
            <p className="px-2 pt-5 pb-3 text-xs font-medium text-muted-foreground">
              Settings
            </p>
            <nav className="flex flex-col gap-1" aria-label="Settings sections">
              {SETTINGS_SECTIONS.map((section) => {
                const Icon = section.icon
                const selected = section.id === activeSection.id
                return (
                  <Button
                    key={section.id}
                    type="button"
                    variant="ghost"
                    className={cn(
                      "h-10 w-full justify-start rounded-lg",
                      selected &&
                        "bg-sidebar-accent text-sidebar-accent-foreground"
                    )}
                    aria-current={selected ? "page" : undefined}
                    onClick={() => onSectionChange(section.id)}
                  >
                    <Icon />
                    {section.label}
                  </Button>
                )
              })}
            </nav>
          </aside>

          <section className="min-h-0 min-w-0 overflow-hidden bg-popover text-popover-foreground">
            {activeSection.id === "general" ? (
              <GeneralSettings onImported={onImported} />
            ) : null}
            {activeSection.id === "models" ? (
              <ModelsSettings
                onModelUnavailable={onModelUnavailable}
                onSelected={onModelSelected}
              />
            ) : null}
          </section>
        </div>
      </DialogContent>
    </Dialog>
  )
}
