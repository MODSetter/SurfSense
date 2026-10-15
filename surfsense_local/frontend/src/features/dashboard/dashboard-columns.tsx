import { createContext, useContext, useRef, type ReactNode } from "react"

import { ResizeHandle } from "@/components/ui/resize-handle"
import { SlideRail } from "@/components/ui/slide-rail"
import { cn } from "@/lib/utils"

import { useColumnWidths } from "./use-column-widths"

type Columns = ReturnType<typeof useColumnWidths>

const ColumnsContext = createContext<Columns | null>(null)

function useColumns(): Columns {
  const columns = useContext(ColumnsContext)
  if (!columns) throw new Error("A dashboard column outside DashboardColumns")
  return columns
}

/**
 * The dashboard's section, which holds the widths of its resizable columns.
 * Only the parts below that read a width render when it changes, so a drag of
 * an edge renders the edges and the column boxes, never what is inside them.
 */
export function DashboardColumns({
  sidebarWide,
  rightPanelOpen,
  rightPanelWide,
  children,
}: {
  // Showing a source preview.
  sidebarWide: boolean
  rightPanelOpen: boolean
  // Showing an inspected citation or artifact.
  rightPanelWide: boolean
  children: ReactNode
}) {
  const sectionRef = useRef<HTMLElement>(null)
  const columns = useColumnWidths(sectionRef, {
    sidebarWide,
    rightPanelOpen,
    rightPanelWide,
  })
  return (
    <section
      ref={sectionRef}
      className="my-2 mr-2 flex min-h-0 min-w-0 overflow-hidden rounded-[16px] border bg-background shadow-sm"
    >
      <ColumnsContext.Provider value={columns}>
        {children}
      </ColumnsContext.Provider>
    </section>
  )
}

/** The left column's box, as wide as the sidebar is now. */
export function SidebarColumn({
  id,
  children,
}: {
  id: string
  children: ReactNode
}) {
  const columns = useColumns()
  return (
    <div
      id={id}
      className={cn(
        "flex h-full min-h-0 min-w-68 flex-col transition-[width] duration-[240ms] ease-[cubic-bezier(0.4,0,0.2,1)] motion-reduce:transition-none",
        !columns.animate && "transition-none"
      )}
      style={{ width: columns.sidebar.width }}
    >
      {children}
    </div>
  )
}

/** The draggable edge of the sidebar, or of the right panel. */
export function ColumnEdge({
  column,
  label,
  controls,
}: {
  column: "sidebar" | "rightPanel"
  label: string
  controls: string
}) {
  const columns = useColumns()
  return (
    <ResizeHandle
      side={column === "sidebar" ? "start" : "end"}
      label={label}
      controls={controls}
      {...columns[column].edge}
    />
  )
}

/** The right panel's rail, as wide as the panel is now. */
export function RightPanelRail({
  open,
  children,
}: {
  open: boolean
  children: ReactNode
}) {
  const columns = useColumns()
  return (
    <SlideRail
      open={open}
      side="end"
      width={columns.rightPanel.width}
      animate={columns.animate}
    >
      {children}
    </SlideRail>
  )
}
