import { useQuery } from "@tanstack/react-query"
import { useMemo, useState } from "react"
import { type Column, DataGrid } from "react-data-grid"
import "react-data-grid/lib/styles.css"

import { Button } from "@/components/ui/button"
import { FileIcon } from "@/components/ui/icons"
import { Spinner } from "@/components/ui/spinner"
import { fileUrl, type ArtifactDetail } from "../api"
import {
  MAX_VIEWER_BYTES,
  ParseWorkbookError,
  parseWorkbook,
  type SheetView,
} from "./parse-workbook"
import { VIEWER_PADDING } from "./viewer-layout"

function columnLabel(index: number): string {
  let n = index
  let label = ""
  while (n >= 0) {
    label = String.fromCharCode((n % 26) + 65) + label
    n = Math.floor(n / 26) - 1
  }
  return label
}

interface GridRow {
  readonly rowNumber: number
  readonly [key: string]: string | number
}

function SpreadsheetGrid({ sheet }: { sheet: SheetView }) {
  const { columns, rows } = useMemo(() => {
    const colCount = Math.max(1, ...sheet.cells.map((row) => row.length))
    const gridColumns: Column<GridRow>[] = [
      { key: "rowNumber", name: "", width: 48, frozen: true },
      ...Array.from({ length: colCount }, (_, col): Column<GridRow> => ({
        key: `column-${col}`,
        name: columnLabel(col),
      })),
    ]
    const gridRows: GridRow[] = sheet.cells.map((row, index) =>
      Object.fromEntries([
        ["rowNumber", index + 1],
        ...row.map((cell, col) => [`column-${col}`, cell.text]),
      ])
    )
    return { columns: gridColumns, rows: gridRows }
  }, [sheet])

  return (
    <DataGrid
      aria-label={`${sheet.name} worksheet`}
      className="rdg-light h-full"
      columns={columns}
      rowKeyGetter={(row) => row.rowNumber}
      rows={rows}
      style={{ blockSize: "100%" }}
    />
  )
}

function fallbackMessage(error: unknown): string {
  if (error instanceof ParseWorkbookError) {
    if (error.code === "oversize") {
      return "This workbook is too large to preview here. Download it to open it."
    }
    return "This workbook could not be opened. Download it to open it."
  }
  return "This spreadsheet can't be previewed here. Download it to open it."
}

export function XlsxViewer({ artifact }: { artifact: ArtifactDetail }) {
  const primary = artifact.files.find((file) => file.role === "primary")

  const {
    data: view,
    error,
    isLoading,
    refetch,
  } = useQuery({
    queryKey: ["artifact-workbook", artifact.id],
    queryFn: async () => {
      if (!primary) throw new Error("This artifact has no file to preview")
      if (primary.size_bytes > MAX_VIEWER_BYTES) {
        throw new ParseWorkbookError(
          "oversize",
          `Workbook is too large to preview (${primary.size_bytes} bytes)`
        )
      }
      const response = await fetch(fileUrl(artifact.id, "primary"))
      if (!response.ok) {
        throw new Error(`Could not load workbook (${response.status})`)
      }
      const buffer = await response.arrayBuffer()
      return parseWorkbook(buffer)
    },
    enabled: primary != null,
  })

  // The selected sheet tab is per-artifact UI state; the "adjust state
  // during render" idiom (see ArtifactList) resets it without an effect.
  const [active, setActive] = useState(0)
  const [renderedArtifactId, setRenderedArtifactId] = useState(artifact.id)
  if (artifact.id !== renderedArtifactId) {
    setRenderedArtifactId(artifact.id)
    setActive(0)
  }

  if (isLoading) {
    return (
      <div className="flex h-full items-center justify-center text-muted-foreground">
        <Spinner className="size-6" />
      </div>
    )
  }

  if (error || !view) {
    return (
      <div
        className={`flex h-full flex-col items-center justify-center gap-3 text-center ${VIEWER_PADDING}`}
      >
        <FileIcon className="size-8 text-muted-foreground" />
        <div>
          <p className="text-sm font-medium">Couldn't open this spreadsheet</p>
          <p className="mt-1 text-xs text-muted-foreground">
            {fallbackMessage(error)}
          </p>
        </div>
        {error &&
        !(error instanceof ParseWorkbookError && error.code === "oversize") ? (
          <Button
            type="button"
            variant="secondary"
            size="sm"
            onClick={() => void refetch()}
          >
            Try again
          </Button>
        ) : null}
      </div>
    )
  }

  const sheet = view.sheets[active] ?? view.sheets[0]

  return (
    <div className="flex h-full min-h-0 flex-col overflow-hidden border bg-white text-neutral-950">
      {view.sheets.length > 1 ? (
        <div
          role="tablist"
          aria-label="Worksheets"
          className="flex shrink-0 gap-1 overflow-x-auto border-b border-neutral-200 px-2 py-1.5"
        >
          {view.sheets.map((entry, index) => (
            <button
              key={entry.name}
              type="button"
              role="tab"
              aria-selected={index === active}
              className={
                index === active
                  ? "rounded-md bg-neutral-100 px-2.5 py-1 text-xs font-medium text-neutral-950"
                  : "rounded-md px-2.5 py-1 text-xs text-neutral-500 hover:bg-neutral-100"
              }
              onClick={() => setActive(index)}
            >
              {entry.name}
            </button>
          ))}
        </div>
      ) : null}

      {sheet.truncated ? (
        <p className="shrink-0 border-b border-neutral-200 px-3 py-1.5 text-xs text-neutral-500">
          Showing the first {sheet.cells.length} rows. Download the file for the
          full workbook.
        </p>
      ) : null}

      <div className="min-h-0 flex-1 overflow-hidden">
        <SpreadsheetGrid sheet={sheet} />
      </div>
    </div>
  )
}
