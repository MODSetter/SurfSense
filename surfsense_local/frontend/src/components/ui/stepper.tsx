import { Slot } from "radix-ui"
import * as React from "react"

import { CheckIcon } from "@/components/ui/icons"
import { Spinner } from "@/components/ui/spinner"
import { cn } from "@/lib/utils"

type StepState = "active" | "completed" | "inactive"

type StepperContextValue = {
  activeStep: number
  setActiveStep: (step: number) => void
  orientation: "horizontal" | "vertical"
}

type StepItemContextValue = {
  step: number
  state: StepState
  isDisabled: boolean
  isLoading: boolean
}

const StepperContext = React.createContext<StepperContextValue | undefined>(
  undefined
)
const StepItemContext = React.createContext<StepItemContextValue | undefined>(
  undefined
)

function useStepper() {
  const context = React.useContext(StepperContext)
  if (!context) {
    throw new Error("useStepper must be used within a Stepper")
  }
  return context
}

function useStepItem() {
  const context = React.useContext(StepItemContext)
  if (!context) {
    throw new Error("useStepItem must be used within a StepperItem")
  }
  return context
}

interface StepperProps extends React.ComponentProps<"div"> {
  defaultValue?: number
  value?: number
  onValueChange?: (value: number) => void
  orientation?: "horizontal" | "vertical"
}

const Stepper = React.forwardRef<HTMLDivElement, StepperProps>(
  (
    {
      defaultValue = 0,
      value,
      onValueChange,
      orientation = "horizontal",
      className,
      ...props
    },
    ref
  ) => {
    const [internalStep, setInternalStep] = React.useState(defaultValue)
    const setActiveStep = React.useCallback(
      (step: number) => {
        if (value === undefined) {
          setInternalStep(step)
        }
        onValueChange?.(step)
      },
      [onValueChange, value]
    )

    return (
      <StepperContext.Provider
        value={{
          activeStep: value ?? internalStep,
          setActiveStep,
          orientation,
        }}
      >
        <div
          ref={ref}
          data-orientation={orientation}
          className={cn(
            "group/stepper inline-flex data-[orientation=horizontal]:w-full data-[orientation=horizontal]:flex-row data-[orientation=vertical]:flex-col",
            className
          )}
          {...props}
        />
      </StepperContext.Provider>
    )
  }
)
Stepper.displayName = "Stepper"

interface StepperItemProps extends React.ComponentProps<"div"> {
  step: number
  completed?: boolean
  disabled?: boolean
  loading?: boolean
}

const StepperItem = React.forwardRef<HTMLDivElement, StepperItemProps>(
  (
    {
      step,
      completed = false,
      disabled = false,
      loading = false,
      className,
      children,
      ...props
    },
    ref
  ) => {
    const { activeStep } = useStepper()
    const state: StepState =
      completed || step < activeStep
        ? "completed"
        : activeStep === step
          ? "active"
          : "inactive"
    const isLoading = loading && step === activeStep

    return (
      <StepItemContext.Provider
        value={{ step, state, isDisabled: disabled, isLoading }}
      >
        <div
          ref={ref}
          data-state={state}
          data-loading={isLoading || undefined}
          className={cn(
            "group/step flex items-center group-data-[orientation=horizontal]/stepper:flex-row group-data-[orientation=vertical]/stepper:flex-col",
            className
          )}
          {...props}
        >
          {children}
        </div>
      </StepItemContext.Provider>
    )
  }
)
StepperItem.displayName = "StepperItem"

interface StepperTriggerProps extends React.ComponentProps<"button"> {
  asChild?: boolean
}

const StepperTrigger = React.forwardRef<HTMLButtonElement, StepperTriggerProps>(
  ({ asChild = false, className, children, onClick, ...props }, ref) => {
    const { setActiveStep } = useStepper()
    const { step, isDisabled } = useStepItem()
    const Comp = asChild ? Slot.Root : "button"

    return (
      <Comp
        ref={ref}
        className={cn(
          "inline-flex items-center gap-3 disabled:pointer-events-none disabled:opacity-50",
          className
        )}
        disabled={isDisabled}
        onClick={(event) => {
          onClick?.(event)
          if (!event.defaultPrevented) {
            setActiveStep(step)
          }
        }}
        {...props}
      >
        {children}
      </Comp>
    )
  }
)
StepperTrigger.displayName = "StepperTrigger"

interface StepperIndicatorProps extends React.ComponentProps<"div"> {
  asChild?: boolean
}

const StepperIndicator = React.forwardRef<
  HTMLDivElement,
  StepperIndicatorProps
>(({ asChild = false, className, children, ...props }, ref) => {
  const { state, step, isLoading } = useStepItem()

  return (
    <div
      ref={ref}
      data-state={state}
      className={cn(
        "relative flex size-6 shrink-0 items-center justify-center rounded-full bg-muted text-xs font-medium text-muted-foreground data-[state=active]:bg-primary data-[state=active]:text-primary-foreground data-[state=completed]:bg-primary data-[state=completed]:text-primary-foreground",
        className
      )}
      {...props}
    >
      {asChild ? (
        children
      ) : (
        <>
          <span className="transition-all group-data-[loading=true]/step:scale-0 group-data-[loading=true]/step:opacity-0 group-data-[loading=true]/step:transition-none group-data-[state=completed]/step:scale-0 group-data-[state=completed]/step:opacity-0">
            {step}
          </span>
          <CheckIcon
            aria-hidden="true"
            className="absolute scale-0 opacity-0 transition-all group-data-[state=completed]/step:scale-100 group-data-[state=completed]/step:opacity-100"
          />
          {isLoading ? (
            <Spinner
              aria-hidden="true"
              className="absolute size-3.5 transition-all"
            />
          ) : null}
        </>
      )}
    </div>
  )
})
StepperIndicator.displayName = "StepperIndicator"

const StepperTitle = React.forwardRef<
  HTMLHeadingElement,
  React.ComponentProps<"h3">
>(({ className, ...props }, ref) => (
  <h3 ref={ref} className={cn("text-sm font-medium", className)} {...props} />
))
StepperTitle.displayName = "StepperTitle"

const StepperDescription = React.forwardRef<
  HTMLParagraphElement,
  React.ComponentProps<"p">
>(({ className, ...props }, ref) => (
  <p
    ref={ref}
    className={cn("text-sm text-muted-foreground", className)}
    {...props}
  />
))
StepperDescription.displayName = "StepperDescription"

const StepperSeparator = React.forwardRef<
  HTMLDivElement,
  React.ComponentProps<"div">
>(({ className, ...props }, ref) => (
  <div
    ref={ref}
    className={cn(
      "m-0.5 bg-muted group-data-[orientation=horizontal]/stepper:h-0.5 group-data-[orientation=horizontal]/stepper:w-full group-data-[orientation=horizontal]/stepper:flex-1 group-data-[orientation=vertical]/stepper:h-12 group-data-[orientation=vertical]/stepper:w-0.5 group-data-[state=completed]/step:bg-primary",
      className
    )}
    {...props}
  />
))
StepperSeparator.displayName = "StepperSeparator"

export {
  Stepper,
  StepperDescription,
  StepperIndicator,
  StepperItem,
  StepperSeparator,
  StepperTitle,
  StepperTrigger,
}
