import { useState, type ComponentType } from "react"

import { useTheme } from "@/components/theme-provider"
import { Button } from "@/components/ui/button"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import {
  ComputerIcon,
  MoonIcon,
  Settings2Icon,
  SunIcon,
} from "@/components/ui/icons"
import { Label } from "@/components/ui/label"
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group"
import { cn } from "@/lib/utils"

type SettingsSection = {
  id: string
  label: string
  icon: ComponentType<{ className?: string; strokeWidth?: number }>
  content: ComponentType
}

const APPEARANCES = [
  {
    value: "system",
    label: "System",
    description: "Match your device",
    icon: ComputerIcon,
  },
  {
    value: "light",
    label: "Light",
    description: "Always use light mode",
    icon: SunIcon,
  },
  {
    value: "dark",
    label: "Dark",
    description: "Always use dark mode",
    icon: MoonIcon,
  },
] as const

type Appearance = (typeof APPEARANCES)[number]["value"]

function GeneralSettings() {
  const { theme, setTheme } = useTheme()

  return (
    <>
      <header className="border-b px-7 py-5">
        <h2 className="font-heading text-lg font-medium text-balance">
          General
        </h2>
        <p className="mt-1 text-sm text-pretty text-muted-foreground">
          Manage your SurfSense preferences.
        </p>
      </header>
      <div className="px-7 py-6">
        <div className="flex flex-col gap-1">
          <h3 className="text-sm font-medium">Appearance</h3>
          <p className="text-sm text-pretty text-muted-foreground">
            Choose how SurfSense looks on this device.
          </p>
        </div>
        <RadioGroup
          className="mt-5 grid grid-cols-3 gap-3"
          value={theme}
          onValueChange={(value) => setTheme(value as Appearance)}
          aria-label="Appearance"
        >
          {APPEARANCES.map((option) => {
            const Icon = option.icon
            return (
              <Label
                key={option.value}
                htmlFor={`theme-${option.value}`}
                className={cn(
                  "relative flex min-h-32 cursor-pointer flex-col items-center justify-center gap-3 rounded-xl border bg-card p-4 text-center text-card-foreground shadow-xs transition-[border-color,box-shadow] hover:border-foreground/25 hover:shadow-sm",
                  theme === option.value &&
                    "border-primary ring-2 ring-primary/15"
                )}
              >
                <RadioGroupItem
                  id={`theme-${option.value}`}
                  value={option.value}
                  className="absolute top-3 right-3"
                />
                <span className="flex size-10 items-center justify-center rounded-lg bg-muted">
                  <Icon className="size-5" strokeWidth={1.5} />
                </span>
                <span className="flex min-w-0 flex-col gap-1.5">
                  <span>{option.label}</span>
                  <span className="text-xs leading-4 font-normal text-muted-foreground">
                    {option.description}
                  </span>
                </span>
              </Label>
            )
          })}
        </RadioGroup>
      </div>
    </>
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
      <DialogContent className="h-[min(640px,calc(100svh-2rem))] w-[min(1000px,calc(100vw-2rem))] max-w-none overflow-hidden rounded-2xl p-0 shadow-xl sm:max-w-none">
        <DialogHeader className="sr-only">
          <DialogTitle>Settings</DialogTitle>
          <DialogDescription>
            Manage your SurfSense preferences.
          </DialogDescription>
        </DialogHeader>

        <div className="grid h-full grid-cols-[184px_minmax(0,1fr)]">
          <aside className="border-r bg-sidebar p-3 text-sidebar-foreground">
            <p className="px-2 pt-2 pb-4 font-heading text-base font-medium">
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

          <section className="min-w-0 overflow-y-auto bg-popover text-popover-foreground">
            <ActiveSection />
          </section>
        </div>
      </DialogContent>
    </Dialog>
  )
}
