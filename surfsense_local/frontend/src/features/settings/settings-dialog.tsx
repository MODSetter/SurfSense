import { useState, type ComponentType } from "react"

import { Button } from "@/components/ui/button"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { Settings2Icon } from "@/components/ui/icons"
import { cn } from "@/lib/utils"

import { AppearanceToggle } from "./appearance-toggle"

type SettingsSection = {
  id: string
  label: string
  icon: ComponentType<{ className?: string; strokeWidth?: number }>
  content: ComponentType
}

function GeneralSettings() {
  return (
    <div className="flex items-center justify-between gap-8 px-7 pt-14 pb-7">
      <div className="flex flex-col gap-1">
        <h3 className="text-sm font-medium">Appearance</h3>
        <p className="text-sm text-pretty text-muted-foreground">
          Choose how SurfSense looks on this device.
        </p>
      </div>
      <AppearanceToggle />
    </div>
  )
}

// Add future settings pages here; the dialog navigation is generated from this list.
const SETTINGS_SECTIONS = [
  {
    id: "general",
    label: "General",
    icon: Settings2Icon,
    content: GeneralSettings,
  },
] satisfies SettingsSection[]

type SectionId = (typeof SETTINGS_SECTIONS)[number]["id"]

export function SettingsDialog({
  open,
  onOpenChange,
}: {
  open: boolean
  onOpenChange: (open: boolean) => void
}) {
  const [activeSectionId, setActiveSectionId] = useState<SectionId>("general")
  const activeSection =
    SETTINGS_SECTIONS.find((section) => section.id === activeSectionId) ??
    SETTINGS_SECTIONS[0]
  const ActiveSection = activeSection.content

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="h-[640px] w-[1000px] max-w-none select-none overflow-hidden rounded-2xl p-0 shadow-xl sm:max-w-none">
        <DialogHeader className="sr-only">
          <DialogTitle>Settings</DialogTitle>
          <DialogDescription>
            Manage your SurfSense preferences.
          </DialogDescription>
        </DialogHeader>

        <div className="grid h-full grid-cols-[184px_minmax(0,1fr)]">
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
                    onClick={() => setActiveSectionId(section.id)}
                  >
                    <Icon />
                    {section.label}
                  </Button>
                )
              })}
            </nav>
          </aside>

          <section className="min-w-0 overflow-y-auto overscroll-contain bg-popover text-popover-foreground">
            <ActiveSection />
          </section>
        </div>
      </DialogContent>
    </Dialog>
  )
}
