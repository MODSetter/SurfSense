import * as React from "react"
import { Popover as PopoverPrimitive } from "radix-ui"

import { CheckIcon, ChevronDownIcon } from "@/components/ui/icons"
import {
  InputGroup,
  InputGroupAddon,
  InputGroupButton,
  InputGroupInput,
} from "@/components/ui/input-group"
import { cn } from "@/lib/utils"

// shadcn ships its Combobox on Base UI, which this app does not depend on, so
// the same API is rebuilt here on the Radix Popover the rest of the UI uses.
type ComboboxFilter = (
  itemValue: string,
  query: string,
  keywords: string[]
) => boolean

const defaultFilter: ComboboxFilter = (itemValue, query, keywords) => {
  const needle = query.trim().toLowerCase()
  if (!needle) return true
  return [itemValue, ...keywords].some((candidate) =>
    candidate.toLowerCase().includes(needle)
  )
}

type ComboboxContextValue = {
  open: boolean
  setOpen: (open: boolean) => void
  value: string | null
  select: (value: string) => void
  inputValue: string
  setInputValue: (value: string) => void
  disabled: boolean
  matches: (itemValue: string, keywords: string[]) => boolean
  register: (itemValue: string, keywords: string[]) => () => void
  visibleCount: number
  listId: string
  activeId: string | null
  setActiveId: (id: string | null) => void
  itemId: (itemValue: string) => string
  listRef: React.RefObject<HTMLDivElement | null>
}

const ComboboxContext = React.createContext<ComboboxContextValue | null>(null)

function useCombobox(part: string) {
  const context = React.useContext(ComboboxContext)
  if (!context) {
    throw new Error(`${part} must be used within a Combobox`)
  }
  return context
}

function Combobox({
  children,
  value,
  onValueChange,
  inputValue,
  onInputValueChange,
  open: openProp,
  onOpenChange,
  filter = defaultFilter,
  disabled = false,
}: {
  children: React.ReactNode
  value?: string | null
  onValueChange?: (value: string) => void
  inputValue: string
  onInputValueChange: (value: string) => void
  open?: boolean
  onOpenChange?: (open: boolean) => void
  filter?: ComboboxFilter
  disabled?: boolean
}) {
  const [uncontrolledOpen, setUncontrolledOpen] = React.useState(false)
  const [activeId, setActiveId] = React.useState<string | null>(null)
  const [items, setItems] = React.useState<Record<string, string[]>>({})
  const listRef = React.useRef<HTMLDivElement>(null)
  const listId = React.useId()

  const open = openProp ?? uncontrolledOpen
  const setOpen = React.useCallback(
    (next: boolean) => {
      if (!next) setActiveId(null)
      setUncontrolledOpen(next)
      onOpenChange?.(next)
    },
    [onOpenChange]
  )

  const matches = React.useCallback(
    (itemValue: string, keywords: string[]) =>
      filter(itemValue, inputValue, keywords),
    [filter, inputValue]
  )

  const register = React.useCallback(
    (itemValue: string, keywords: string[]) => {
      setItems((current) => ({ ...current, [itemValue]: keywords }))
      return () => {
        setItems((current) => {
          const next = { ...current }
          delete next[itemValue]
          return next
        })
      }
    },
    []
  )

  const itemId = React.useCallback(
    (itemValue: string) => `${listId}-${encodeURIComponent(itemValue)}`,
    [listId]
  )

  const select = React.useCallback(
    (next: string) => {
      onValueChange?.(next)
      onInputValueChange(next)
      setOpen(false)
    },
    [onInputValueChange, onValueChange, setOpen]
  )

  const visibleCount = Object.entries(items).filter(([itemValue, keywords]) =>
    matches(itemValue, keywords)
  ).length

  const context: ComboboxContextValue = {
    open,
    setOpen,
    value: value ?? null,
    select,
    inputValue,
    setInputValue: onInputValueChange,
    disabled,
    matches,
    register,
    visibleCount,
    listId,
    activeId,
    setActiveId,
    itemId,
    listRef,
  }

  return (
    <ComboboxContext.Provider value={context}>
      <PopoverPrimitive.Root open={open} onOpenChange={setOpen}>
        {children}
      </PopoverPrimitive.Root>
    </ComboboxContext.Provider>
  )
}

function ComboboxInput({
  className,
  showTrigger = true,
  onKeyDown,
  ...props
}: React.ComponentProps<"input"> & { showTrigger?: boolean }) {
  const combobox = useCombobox("ComboboxInput")
  const { open, setOpen, setActiveId, listRef, select, disabled } = combobox

  const move = (direction: 1 | -1) => {
    const options = listRef.current?.querySelectorAll<HTMLElement>(
      '[data-slot="combobox-item"]:not([hidden])'
    )
    if (!options?.length) return
    const current = [...options].findIndex(
      (option) => option.id === combobox.activeId
    )
    const next =
      current === -1
        ? direction === 1
          ? 0
          : options.length - 1
        : (current + direction + options.length) % options.length
    const option = options[next]
    setActiveId(option.id)
    option.scrollIntoView?.({ block: "nearest" })
  }

  return (
    <PopoverPrimitive.Anchor asChild>
      <InputGroup className={cn("w-auto", className)}>
        <InputGroupInput
          role="combobox"
          autoComplete="off"
          aria-expanded={open}
          aria-controls={combobox.listId}
          aria-autocomplete="list"
          aria-activedescendant={
            open ? (combobox.activeId ?? undefined) : undefined
          }
          disabled={disabled}
          value={combobox.inputValue}
          onChange={(event) => {
            combobox.setInputValue(event.target.value)
            setActiveId(null)
            if (!open) setOpen(true)
          }}
          onClick={() => {
            if (!open && !disabled) setOpen(true)
          }}
          onKeyDown={(event) => {
            onKeyDown?.(event)
            if (event.defaultPrevented) return
            if (event.key === "ArrowDown" || event.key === "ArrowUp") {
              event.preventDefault()
              if (!open) {
                setOpen(true)
                return
              }
              move(event.key === "ArrowDown" ? 1 : -1)
              return
            }
            if (event.key === "Enter" && open && combobox.activeId) {
              const option = listRef.current?.querySelector<HTMLElement>(
                `#${CSS.escape(combobox.activeId)}`
              )
              if (
                option?.dataset.value &&
                option.dataset.disabled === undefined
              ) {
                event.preventDefault()
                select(option.dataset.value)
              }
              return
            }
            if (event.key === "Escape" && open) {
              event.preventDefault()
              setOpen(false)
            }
          }}
          {...props}
        />
        {showTrigger ? (
          <InputGroupAddon align="inline-end">
            <PopoverPrimitive.Trigger asChild>
              <InputGroupButton
                size="icon-xs"
                variant="ghost"
                disabled={disabled}
                tabIndex={-1}
                data-slot="combobox-trigger"
              >
                <ChevronDownIcon className="text-muted-foreground" />
              </InputGroupButton>
            </PopoverPrimitive.Trigger>
          </InputGroupAddon>
        ) : null}
      </InputGroup>
    </PopoverPrimitive.Anchor>
  )
}

function ComboboxContent({
  className,
  align = "start",
  sideOffset = 6,
  container,
  ...props
}: React.ComponentProps<typeof PopoverPrimitive.Content> & {
  // Inside a modal Dialog, pass a host element within the dialog: the dialog's
  // scroll lock only lets wheel events through for targets it contains, so a
  // popup portalled to the body cannot scroll its own list.
  container?: React.ComponentProps<typeof PopoverPrimitive.Portal>["container"]
}) {
  useCombobox("ComboboxContent")
  return (
    <PopoverPrimitive.Portal container={container}>
      <PopoverPrimitive.Content
        data-slot="combobox-content"
        align={align}
        sideOffset={sideOffset}
        // The input keeps focus so typing continues to filter the list.
        onOpenAutoFocus={(event) => event.preventDefault()}
        onCloseAutoFocus={(event) => event.preventDefault()}
        className={cn(
          "z-50 max-h-(--radix-popover-content-available-height) w-(--radix-popover-trigger-width) origin-(--radix-popover-content-transform-origin) overflow-hidden rounded-lg bg-popover p-1 text-popover-foreground shadow-md ring-1 ring-foreground/10 duration-100 data-[side=bottom]:slide-in-from-top-2 data-[side=top]:slide-in-from-bottom-2 data-open:animate-in data-open:fade-in-0 data-open:zoom-in-95 data-closed:animate-out data-closed:fade-out-0 data-closed:zoom-out-95",
          className
        )}
        {...props}
      />
    </PopoverPrimitive.Portal>
  )
}

function ComboboxList({ className, ...props }: React.ComponentProps<"div">) {
  const { listRef, listId } = useCombobox("ComboboxList")
  return (
    <div
      ref={listRef}
      id={listId}
      role="listbox"
      data-slot="combobox-list"
      className={cn(
        "max-h-60 scroll-py-1 overflow-y-auto overscroll-contain",
        className
      )}
      {...props}
    />
  )
}

function ComboboxGroup({ className, ...props }: React.ComponentProps<"div">) {
  // Hidden wholesale when the query matches nothing, so its label does not
  // caption an empty list.
  const { visibleCount } = useCombobox("ComboboxGroup")
  return (
    <div
      role="group"
      data-slot="combobox-group"
      hidden={visibleCount === 0}
      className={cn(className)}
      {...props}
    />
  )
}

function ComboboxLabel({ className, ...props }: React.ComponentProps<"div">) {
  return (
    <div
      data-slot="combobox-label"
      className={cn(
        "px-1.5 py-1 text-xs font-medium text-muted-foreground",
        className
      )}
      {...props}
    />
  )
}

function ComboboxItem({
  className,
  children,
  value,
  keywords = [],
  disabled = false,
  onClick,
  ...props
}: Omit<React.ComponentProps<"div">, "onSelect"> & {
  value: string
  keywords?: string[]
  /** Listed and findable, but never selected. */
  disabled?: boolean
}) {
  const combobox = useCombobox("ComboboxItem")
  const { register, matches, select, setActiveId, activeId, itemId } = combobox
  const id = itemId(value)
  // Keywords are stable per item in practice; joined so the effect is not
  // re-run on every render by a fresh array literal.
  const keywordKey = keywords.join(" ")

  React.useEffect(
    () => register(value, keywordKey ? keywordKey.split(" ") : []),
    [register, value, keywordKey]
  )

  const visible = matches(value, keywords)
  const selected = combobox.value === value

  return (
    <div
      id={id}
      role="option"
      data-slot="combobox-item"
      data-value={value}
      data-highlighted={activeId === id ? "" : undefined}
      data-disabled={disabled ? "" : undefined}
      aria-selected={selected}
      aria-disabled={disabled || undefined}
      hidden={!visible}
      className={cn(
        "relative flex w-full cursor-default items-center gap-1.5 rounded-md py-1 pr-8 pl-1.5 text-sm outline-hidden select-none data-highlighted:bg-accent data-highlighted:text-accent-foreground data-highlighted:**:text-accent-foreground data-disabled:opacity-60 [&_svg]:pointer-events-none [&_svg]:shrink-0 [&_svg:not([class*='size-'])]:size-4",
        className
      )}
      onPointerMove={() => setActiveId(id)}
      // Selecting on pointer down keeps the input from losing focus first.
      onPointerDown={(event) => event.preventDefault()}
      onClick={(event) => {
        onClick?.(event)
        if (!disabled) select(value)
      }}
      {...props}
    >
      {children}
      {selected ? (
        <span className="pointer-events-none absolute right-2 flex items-center justify-center">
          <CheckIcon />
        </span>
      ) : null}
    </div>
  )
}

function ComboboxEmpty({ className, ...props }: React.ComponentProps<"div">) {
  const { visibleCount } = useCombobox("ComboboxEmpty")
  if (visibleCount > 0) return null
  return (
    <div
      data-slot="combobox-empty"
      className={cn(
        "flex w-full justify-center py-2 text-center text-sm text-muted-foreground",
        className
      )}
      {...props}
    />
  )
}

function ComboboxSeparator({
  className,
  ...props
}: React.ComponentProps<"div">) {
  return (
    <div
      data-slot="combobox-separator"
      className={cn("-mx-1 my-1 h-px bg-border", className)}
      {...props}
    />
  )
}

export {
  Combobox,
  ComboboxInput,
  ComboboxContent,
  ComboboxList,
  ComboboxGroup,
  ComboboxLabel,
  ComboboxItem,
  ComboboxEmpty,
  ComboboxSeparator,
}
