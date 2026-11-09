import { createContext, useContext, useRef, type ReactNode } from "react"

import { ResizeHandle } from "@/components/ui/resize-handle"
import { SlideRail } from "@/components/ui/slide-rail"
import { cn } from "@/lib/utils"

import { useColumnWidths } from "./use-column-widths"
import { useSidebarPeek } from "./use-sidebar-peek"

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
  sidebarOpen,
  sidebarWide,
  rightPanelOpen,
  rightPanelWide,
  children,
}: {
  sidebarOpen: boolean
  // Showing a source preview.
  sidebarWide: boolean
  rightPanelOpen: boolean
  // Showing an inspected citation or artifact.
  rightPanelWide: boolean
  children: ReactNode
}) {
  const sectionRef = useRef<HTMLElement>(null)
  const columns = useColumnWidths(sectionRef, {
    sidebarOpen,
    sidebarWide,
    rightPanelOpen,
    rightPanelWide,
  })
  return (
    <section
      ref={sectionRef}
      // Clip, not hidden: a hidden box can still be scrolled from code, and
      // PDF.js scrolls the nearest positioned box when its page fits.
      className="relative my-(--columns-gap) mr-2 flex min-h-0 min-w-0 overflow-clip rounded-[16px] border bg-background shadow-sm"
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
  peekable = false,
  children,
}: {
  id: string
  // Hidden, it floats in at the left edge. The startup frame has nothing to press.
  peekable?: boolean
  children: ReactNode
}) {
  const columns = useColumns()
  const { open, width } = columns.sidebar
  const panelRef = useRef<HTMLDivElement>(null)
  const { peeking, edgeProps } = useSidebarPeek(panelRef, !open && peekable)
  return (
    <div
      id={id}
      className={cn(
        "flex h-full min-h-0 flex-col transition-[width,min-width] duration-240 ease-in-out motion-reduce:transition-none",
        open ? "min-w-68" : "min-w-0",
        !columns.animate && "transition-none"
      )}
      style={{ width: open ? width : 0 }}
    >
      {/* One box in every state, so the sidebar inside keeps its scroll and dialogs. */}
      <div
        ref={panelRef}
        inert={(!open && !peeking) || undefined}
        className={cn(
          "flex min-h-0 flex-col",
          open
            ? "h-full"
            : // The section's own 16 px corners; dark needs a deeper shadow to show.
              "absolute inset-y-2 left-2 z-30 overflow-hidden rounded-[16px] border bg-background shadow-lg shadow-black/10 transition-transform duration-200 ease-out motion-reduce:transition-none dark:shadow-black/50 [&_aside]:border-r-0",
          !open && !peeking && "-translate-x-[calc(100%+1rem)]"
        )}
        style={open ? undefined : { width }}
      >
        {children}
      </div>
      {!open && peekable ? (
        <>
          {/* The chat's left edge, and the window's: the far side of the rail. */}
          <div {...edgeProps} className="absolute inset-y-0 left-0 z-20 w-2" />
          <div {...edgeProps} className="fixed inset-y-0 left-0 z-20 w-2" />
        </>
      ) : null}
    </div>
  )
}

/** The chat's column, which takes what the other two leave. */
export function ChatColumn({ children }: { children: ReactNode }) {
  return (
    <div className="flex min-h-0 min-w-130 flex-1 flex-col">{children}</div>
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
