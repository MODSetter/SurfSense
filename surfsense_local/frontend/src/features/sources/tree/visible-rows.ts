import type { WorkspaceDocument } from "../api"
import type { SourceFolder } from "./folders-api"
import { TOP, chainOf, type FolderKey, type SourceIndex } from "./source-index"

type Placement = {
  key: string
  level: number
  parent: FolderKey
  setSize: number
  posInSet: number
}

export type TreeRow =
  | (Placement & {
      kind: "folder"
      folder: SourceFolder
      expanded: boolean
      hasChildren: boolean
    })
  | (Placement & { kind: "document"; document: WorkspaceDocument })

export const folderKey = (id: number) => `folder:${id}`
export const documentKey = (id: number) => `document:${id}`

// Folded the way the server folds names: composed, then case-folded.
export function foldName(name: string) {
  return name.normalize("NFC").toLocaleLowerCase()
}

/**
 * The rows on screen, top to bottom. With a filter, only matches and the
 * folders holding them show, opened; a matching folder opens as the user left it.
 */
export function visibleRows(
  index: SourceIndex,
  expanded: ReadonlySet<number>,
  filter: string
): TreeRow[] {
  const query = foldName(filter.trim())
  const matches = (name: string) => foldName(name).includes(query)
  // Folders that hold a match somewhere below them.
  const holding = new Set<number>()
  if (query) {
    for (const [folder, documents] of index.childDocuments) {
      if (documents.some((document) => matches(document.title))) {
        for (const id of chainOf(index, folder)) holding.add(id)
      }
    }
    for (const folder of index.folders.values()) {
      if (matches(folder.name)) {
        for (const id of chainOf(index, index.parentOf.get(folder.id) ?? TOP)) {
          holding.add(id)
        }
      }
    }
  }

  const rows: TreeRow[] = []
  const walk = (key: FolderKey, level: number, filtered: boolean) => {
    const folders = (index.childFolders.get(key) ?? []).filter(
      (id) =>
        !filtered ||
        holding.has(id) ||
        matches((index.folders.get(id) as SourceFolder).name)
    )
    const documents = (index.childDocuments.get(key) ?? []).filter(
      (document) => !filtered || matches(document.title)
    )
    const setSize = folders.length + documents.length
    let position = 0
    for (const id of folders) {
      const folder = index.folders.get(id) as SourceFolder
      const opened = filtered && holding.has(id)
      const isExpanded = opened || expanded.has(id)
      rows.push({
        kind: "folder",
        key: folderKey(id),
        level,
        parent: key,
        setSize,
        posInSet: ++position,
        folder,
        expanded: isExpanded,
        hasChildren:
          (index.childFolders.get(id)?.length ?? 0) > 0 ||
          (index.childDocuments.get(id)?.length ?? 0) > 0,
      })
      if (isExpanded) walk(id, level + 1, opened)
    }
    for (const document of documents) {
      rows.push({
        kind: "document",
        key: documentKey(document.id),
        level,
        parent: key,
        setSize,
        posInSet: ++position,
        document,
      })
    }
  }
  walk(TOP, 1, query.length > 0)
  return rows
}
