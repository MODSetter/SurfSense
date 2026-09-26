import { createContext, use, useState, type ReactNode } from "react"

// Undefined for an uncontrolled dialog, whose content never changes on close.
const DialogOpenContext = createContext<boolean | undefined>(undefined)

export function DialogOpenScope({
  open,
  children,
}: {
  open: boolean | undefined
  children: ReactNode
}) {
  return <DialogOpenContext value={open}>{children}</DialogOpenContext>
}

// Callers clear a dialog's data in the same update that closes it; the popup
// keeps what it showed while open until its exit animation unmounts it.
export function useContentThroughExit(children: ReactNode) {
  const open = use(DialogOpenContext)
  const [shown, setShown] = useState(children)
  if (open !== false && children !== shown) setShown(children)
  return open === false ? shown : children
}
