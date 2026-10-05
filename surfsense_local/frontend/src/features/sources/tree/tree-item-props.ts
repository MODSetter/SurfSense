import type { HTMLAttributes } from "react"

/** What the tree puts on each row's element: role, level, focus and drag. */
export type TreeItemProps = HTMLAttributes<HTMLLIElement> & {
  "data-drop-folder"?: number
}
