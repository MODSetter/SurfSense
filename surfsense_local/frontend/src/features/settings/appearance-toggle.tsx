import { useTheme } from "@/components/theme-provider"
import { ComputerIcon, MoonIcon, SunIcon } from "@/components/ui/icons"
import { SegmentedControl } from "@/components/ui/segmented-control"
import { intl } from "@/i18n/intl"

const THEME_OPTIONS = [
  { icon: ComputerIcon, value: "system" },
  { icon: SunIcon, value: "light" },
  { icon: MoonIcon, value: "dark" },
] as const

const SWITCH_TO_THEME_ARIA: Record<
  (typeof THEME_OPTIONS)[number]["value"],
  () => string
> = {
  system: () =>
    intl.formatMessage({
      id: "settings_appearance_switch_to_system_aria",
      defaultMessage: "Switch to system theme",
    }),
  light: () =>
    intl.formatMessage({
      id: "settings_appearance_switch_to_light_aria",
      defaultMessage: "Switch to light theme",
    }),
  dark: () =>
    intl.formatMessage({
      id: "settings_appearance_switch_to_dark_aria",
      defaultMessage: "Switch to dark theme",
    }),
}

export function AppearanceToggle() {
  const { theme, setTheme } = useTheme()
  const selectedIndex = THEME_OPTIONS.findIndex(
    (option) => option.value === theme
  )

  return (
    <SegmentedControl
      count={THEME_OPTIONS.length}
      selectedIndex={selectedIndex}
      role="radiogroup"
      aria-label={intl.formatMessage({
        id: "settings_appearance_toggle_aria",
        defaultMessage: "Appearance",
      })}
    >
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
              aria-label={SWITCH_TO_THEME_ARIA[option.value]()}
              onChange={() => setTheme(option.value)}
            />
            <span className="relative flex size-7 items-center justify-center rounded-md peer-focus-visible:z-10 peer-focus-visible:ring-2 peer-focus-visible:ring-ring peer-focus-visible:outline-none">
              <Icon className="size-3.5" strokeWidth={1.5} />
            </span>
          </label>
        )
      })}
    </SegmentedControl>
  )
}
