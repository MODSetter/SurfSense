import { Toaster as Sonner, type ToasterProps } from "sonner"
import { useTheme } from "@/components/theme-provider"
import { CheckCircle2Icon } from "@/components/ui/icons"

function Toaster(props: ToasterProps) {
  const { theme } = useTheme()

  return (
    <Sonner
      theme={theme}
      className="toaster group"
      // Without this, every type (success/error/warning/info) renders with
      // the same --normal-* colors below — error looked identical to a
      // plain toast. This turns on sonner's own per-type palette.
      richColors
      icons={{ success: <CheckCircle2Icon className="size-4" /> }}
      style={
        {
          "--normal-bg": "var(--popover)",
          "--normal-text": "var(--popover-foreground)",
          "--normal-border": "var(--border)",
          "--border-radius": "var(--radius)",
        } as React.CSSProperties
      }
      {...props}
    />
  )
}

export { Toaster }
