import type { HTMLAttributes, KeyboardEvent } from "react"

// Each level indents by this much, past the first.
const INDENT_PX = 16

/**
 * What a row tells its tree. One object for the tree's life, so a memoized
 * row renders again only when its own values change.
 */
export type TreeRowEvents = {
  // Returns the row's release, for React to call when the row unmounts.
  register: (key: string, node: HTMLLIElement) => () => void
  focused: (key: string) => void
  keyDown: (event: KeyboardEvent<HTMLLIElement>, key: string) => void
}

/** Where a row sits, as plain values a memoized row compares cheaply. */
export type TreePlace = {
  rowKey: string
  level: number
  setSize: number
  posInSet: number
  // The one row the Tab key reaches.
  tabbable: boolean
}

/** The attributes that make an `li` a row of the tree, with its focus and keys. */
export function treeItemProps(
  { rowKey, level, setSize, posInSet, tabbable }: TreePlace,
  {
    label,
    checked,
    expanded,
  }: {
    label: string
    // The row has focus, not its checkbox, so the row says what Space ticks.
    checked: boolean | "true" | "false" | "mixed" | undefined
    expanded?: boolean
  },
  events: TreeRowEvents
): HTMLAttributes<HTMLLIElement> {
  return {
    role: "treeitem",
    "aria-level": level,
    "aria-setsize": setSize,
    "aria-posinset": posInSet,
    "aria-expanded": expanded,
    "aria-checked": checked,
    "aria-label": label,
    tabIndex: tabbable ? 0 : -1,
    style:
      level > 1
        ? { paddingInlineStart: 4 + (level - 1) * INDENT_PX }
        : undefined,
    onFocus: (event) => {
      if (event.target === event.currentTarget) events.focused(rowKey)
    },
    onKeyDown: (event) => events.keyDown(event, rowKey),
  }
}
