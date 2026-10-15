import { fireEvent } from "@testing-library/react"

type FakeItem = {
  kind: "file" | "string"
  type: string
  getAsFile: () => File | null
  webkitGetAsEntry: () => unknown
}

/**
 * A DataTransfer as Chromium hands one out, for jsdom, which has none. Files
 * dropped from the desktop come with `files` and `items`; a folder's item
 * gives its entry. A row dragged in the app carries only what it sets.
 */
export function fakeDataTransfer({
  files = [],
  entries = [],
  types,
}: {
  files?: File[]
  // A dropped folder's entry, as `webkitGetAsEntry` gives it.
  entries?: unknown[]
  types?: string[]
} = {}) {
  const data = new Map<string, string>()
  const items: FakeItem[] = [
    ...files.map((file) => ({
      kind: "file" as const,
      type: file.type,
      getAsFile: () => file,
      webkitGetAsEntry: () => null,
    })),
    ...entries.map((entry) => ({
      kind: "file" as const,
      type: "",
      getAsFile: () => null,
      webkitGetAsEntry: () => entry,
    })),
  ]
  const fromDesktop = files.length + entries.length > 0
  return {
    get types() {
      return types ?? [...(fromDesktop ? ["Files"] : []), ...data.keys()]
    },
    files,
    items,
    setData: (type: string, value: string) => void data.set(type, value),
    getData: (type: string) => data.get(type) ?? "",
    setDragImage: () => {},
    effectAllowed: "all",
    dropEffect: "none",
  }
}

/** Drags onto `target` and drops there, in the browser's event order. */
export function dropOn(
  target: Element,
  dataTransfer: ReturnType<typeof fakeDataTransfer>
) {
  fireEvent.dragEnter(target, { dataTransfer })
  fireEvent.dragOver(target, { dataTransfer })
  fireEvent.drop(target, { dataTransfer })
}
