import { Button as ButtonPrimitive } from "@base-ui/react/button"
import { cva, type VariantProps } from "class-variance-authority"
import { cn } from "@/lib/utils"

// Colours ease out in 150ms. Scale presses in the same way but returns over
// 250ms on a no-overshoot spring curve: the held state's timing applies while
// pressed, the resting one on release. No bounce, since a tap carries no momentum.
const TRANSITION =
  "transition-[color,background-color,border-color,box-shadow,opacity,scale] duration-[150ms,150ms,150ms,150ms,150ms,250ms] ease-[ease-out,ease-out,ease-out,ease-out,ease-out,cubic-bezier(0.2,0,0,1)] active:duration-150 active:ease-out"

const buttonVariants = cva(
  `${TRANSITION} group/button inline-flex shrink-0 cursor-pointer items-center justify-center rounded-lg border border-transparent bg-clip-padding text-sm font-medium whitespace-nowrap outline-none select-none focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50 disabled:pointer-events-none disabled:opacity-50 aria-invalid:border-destructive aria-invalid:ring-3 aria-invalid:ring-destructive/20 dark:aria-invalid:border-destructive/50 dark:aria-invalid:ring-destructive/40 [&_svg]:pointer-events-none [&_svg]:shrink-0 [&_svg:not([class*='size-'])]:size-4`,
  {
    variants: {
      variant: {
        default: "bg-primary text-primary-foreground hover:bg-primary/80",
        outline:
          "border-border bg-background hover:bg-muted hover:text-foreground aria-expanded:bg-muted aria-expanded:text-foreground dark:border-input dark:bg-input/30 dark:hover:bg-input/50",
        secondary:
          "bg-secondary text-secondary-foreground hover:bg-[color-mix(in_oklch,var(--secondary),var(--foreground)_5%)] aria-expanded:bg-secondary aria-expanded:text-secondary-foreground",
        ghost:
          "hover:bg-muted hover:text-foreground aria-expanded:bg-muted aria-expanded:text-foreground dark:hover:bg-muted/50",
        destructive:
          "bg-destructive/10 text-destructive hover:bg-destructive/20 focus-visible:border-destructive/40 focus-visible:ring-destructive/20 dark:bg-destructive/20 dark:hover:bg-destructive/30 dark:focus-visible:ring-destructive/40",
        link: "text-primary underline-offset-4 hover:underline",
      },
      size: {
        default:
          "h-8 gap-1.5 px-2.5 has-data-[icon=inline-end]:pr-2 has-data-[icon=inline-start]:pl-2",
        xs: "h-6 gap-1 rounded-[min(var(--radius-md),10px)] px-2 text-xs in-data-[slot=button-group]:rounded-lg has-data-[icon=inline-end]:pr-1.5 has-data-[icon=inline-start]:pl-1.5 [&_svg:not([class*='size-'])]:size-3",
        sm: "h-7 gap-1 rounded-[min(var(--radius-md),12px)] px-2.5 text-[0.8rem] in-data-[slot=button-group]:rounded-lg has-data-[icon=inline-end]:pr-1.5 has-data-[icon=inline-start]:pl-1.5 [&_svg:not([class*='size-'])]:size-3.5",
        lg: "h-9 gap-1.5 px-2.5 has-data-[icon=inline-end]:pr-2 has-data-[icon=inline-start]:pl-2",
        xl: "h-10 gap-2 px-3 text-base has-data-[icon=inline-end]:pr-2.5 has-data-[icon=inline-start]:pl-2.5 [&_svg:not([class*='size-'])]:size-4.5",
        "2xl":
          "h-11 gap-2 px-3.5 text-lg has-data-[icon=inline-end]:pr-3 has-data-[icon=inline-start]:pl-3 [&_svg:not([class*='size-'])]:size-5",
        icon: "size-8",
        "icon-xs":
          "size-6 rounded-[min(var(--radius-md),10px)] in-data-[slot=button-group]:rounded-lg [&_svg:not([class*='size-'])]:size-3",
        "icon-sm":
          "size-7 rounded-[min(var(--radius-md),12px)] in-data-[slot=button-group]:rounded-lg",
        "icon-lg": "size-9",
        "icon-xl": "size-10 [&_svg:not([class*='size-'])]:size-4.5",
        "icon-2xl": "size-11 [&_svg:not([class*='size-'])]:size-5",
      },
    },
    defaultVariants: {
      variant: "default",
      size: "default",
    },
  }
)

type Variant = NonNullable<VariantProps<typeof buttonVariants>["variant"]>

// The press every button shares, popup triggers included. 0.95 is the polish
// guide's floor: deeper reads as exaggerated.
const PRESS_SCALE =
  "active:not-disabled:scale-[0.95] motion-reduce:active:scale-100"

// A static button presses by colour instead, one step past its hover.
const PRESSED_FILL: Record<Variant | "bare", string> = {
  default: "active:bg-primary/70",
  outline: "active:bg-accent dark:active:bg-input/70",
  secondary:
    "active:bg-[color-mix(in_oklch,var(--secondary),var(--foreground)_10%)]",
  ghost: "active:bg-accent dark:active:bg-muted",
  destructive: "active:bg-destructive/25 dark:active:bg-destructive/40",
  link: "",
  bare: "",
}

// Behaviour without looks, for an element that brings its own layout: a card,
// a stretched row link, a flip surface. Keeps the focus ring and the transition.
const BARE = `${TRANSITION} cursor-pointer outline-none focus-visible:ring-3 focus-visible:ring-ring/50 disabled:pointer-events-none disabled:opacity-50`

function Button({
  className,
  variant = "default",
  size = "default",
  static: isStatic = false,
  ...props
}: ButtonPrimitive.Props &
  Omit<VariantProps<typeof buttonVariants>, "variant"> & {
    variant?: Variant | "bare"
    /** No press scale, for wide buttons and rows where 4% is a visible jump. */
    static?: boolean
  }) {
  return (
    <ButtonPrimitive
      data-slot="button"
      data-variant={variant}
      data-size={variant === "bare" ? undefined : size}
      className={cn(
        variant === "bare" ? BARE : buttonVariants({ variant, size }),
        isStatic ? PRESSED_FILL[variant] : PRESS_SCALE,
        className
      )}
      {...props}
    />
  )
}

export { Button, buttonVariants }
