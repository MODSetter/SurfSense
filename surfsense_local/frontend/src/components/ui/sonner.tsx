import { createPortal } from "react-dom"
import { Toaster as Sonner, type ToasterProps } from "sonner"
import { useTheme } from "@/components/theme-provider"
import { CheckCircle2Icon } from "@/components/ui/icons"

function Toaster(props: ToasterProps) {
  const { theme } = useTheme()

  // Outside the isolated #root, so toasts stay above open dialogs.
  return createPortal(
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
    />,
    document.body
  )
}

export { Toaster }
