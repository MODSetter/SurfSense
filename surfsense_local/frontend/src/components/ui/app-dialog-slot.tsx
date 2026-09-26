import {
  createContext,
  use,
  useEffect,
  useId,
  useState,
  useSyncExternalStore,
  type ComponentType,
  type ReactNode,
} from "react"

// For dialogs with no parent in the tree (APP_DIALOGS in main.tsx: egress
// consent, the bug report) that can open over any dialog. Base UI nests only
// what renders inside a popup, so the deepest open popup renders them; nested,
// the parent steps back instead of two modals stacking. Not a Base UI primitive.

type Slot = { id: string; depth: number }

function createSlots() {
  let slots: Slot[] = []
  const listeners = new Set<() => void>()
  const emit = () => listeners.forEach((listener) => listener())
  return {
    subscribe(listener: () => void) {
      listeners.add(listener)
      return () => void listeners.delete(listener)
    },
    add(slot: Slot) {
      slots = [...slots, slot]
      emit()
      return () => {
        slots = slots.filter((other) => other !== slot)
        emit()
      }
    },
    // Deepest wins; between equals, the one opened last.
    top() {
      return slots.reduce<Slot | undefined>(
        (top, slot) => (!top || slot.depth >= top.depth ? slot : top),
        undefined
      )?.id
    },
  }
}

type AppDialogsValue = {
  dialogs: ComponentType[]
  slots: ReturnType<typeof createSlots>
}

const AppDialogsContext = createContext<AppDialogsValue | null>(null)
// Null inside an app dialog, which hosts none of them, itself included.
const DepthContext = createContext<number | null>(0)

// `dialogs` are rendered where they nest, so each keeps its state outside
// itself: it remounts whenever the dialog it opens over changes.
export function AppDialogs({
  dialogs,
  children,
}: {
  dialogs: ComponentType[]
  children: ReactNode
}) {
  const [value] = useState(() => ({ dialogs, slots: createSlots() }))
  return (
    <AppDialogsContext value={value}>
      {children}
      <AppDialogSlot depth={0} />
    </AppDialogsContext>
  )
}

// Wraps a popup's content, so dialogs opened inside it sit one level deeper.
export function AppDialogHost({ children }: { children: ReactNode }) {
  const depth = use(DepthContext)
  if (depth === null) return children
  return (
    <DepthContext value={depth + 1}>
      {children}
      <AppDialogSlot depth={depth + 1} />
    </DepthContext>
  )
}

const noSubscription = () => () => {}

function AppDialogSlot({ depth }: { depth: number }) {
  const app = use(AppDialogsContext)
  const id = useId()
  const isTop = useSyncExternalStore(
    app?.slots.subscribe ?? noSubscription,
    () => app?.slots.top() === id
  )
  useEffect(() => app?.slots.add({ id, depth }), [app, id, depth])

  if (!app || !isTop) return null
  return (
    <DepthContext value={null}>
      {app.dialogs.map((AppDialog, index) => (
        <AppDialog key={index} />
      ))}
    </DepthContext>
  )
}
