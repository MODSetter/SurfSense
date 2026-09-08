import { useTheme } from "@/components/theme-provider"
import { ComputerIcon, MoonIcon, SunIcon } from "@/components/ui/icons"
import { cn } from "@/lib/utils"

const THEME_OPTIONS = [
  { icon: ComputerIcon, value: "system", label: "system" },
  { icon: SunIcon, value: "light", label: "light" },
  { icon: MoonIcon, value: "dark", label: "dark" },
] as const

export function AppearanceToggle() {
  const { theme, setTheme } = useTheme()
  const selectedIndex = THEME_OPTIONS.findIndex(
    (option) => option.value === theme
  )

  return (
    <div
      className="relative inline-flex items-center overflow-hidden rounded-md border bg-muted/80"
      role="radiogroup"
      aria-label="Appearance"
    >
      <span
        aria-hidden="true"
        className="pointer-events-none absolute inset-y-0 left-0 size-7 rounded-md border border-input bg-accent shadow-sm transition-transform duration-300 ease-out motion-reduce:transition-none"
        style={{ translate: `${selectedIndex * 1.75}rem` }}
      />
      {THEME_OPTIONS.map((option) => {
        const Icon = option.icon
        const selected = theme === option.value

        return (
          <label key={option.value} className="relative size-7 cursor-pointer">
            <input
              type="radio"
              name="appearance"
              value={option.value}
              checked={selected}
              className="peer sr-only"
              aria-label={`Switch to ${option.label} theme`}
              onChange={() => setTheme(option.value)}
            />
            <span
              className={cn(
                "relative flex size-7 items-center justify-center rounded-md text-muted-foreground transition-colors peer-focus-visible:z-10 peer-focus-visible:ring-2 peer-focus-visible:ring-ring peer-focus-visible:outline-none",
                selected ? "text-accent-foreground" : "hover:text-foreground"
              )}
            >
              <Icon className="size-3.5" strokeWidth={1.5} />
            </span>
          </label>
        )
      })}
    </div>
  )
}
