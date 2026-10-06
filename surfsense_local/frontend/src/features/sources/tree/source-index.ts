import type { WorkspaceDocument } from "../api"
import type { SourceFolder } from "./folders-api"

/** The Library's top level: where a root's own folder and unfiled sources sit. */
export const TOP = null
export type FolderKey = number | typeof TOP

/** The workspace's folders and sources as a tree, keyed both ways. */
export type SourceIndex = {
  // The root folder whose children are the top level; null with no folders.
  rootFolderId: number | null
  folders: ReadonlyMap<number, SourceFolder>
  parentOf: ReadonlyMap<number, FolderKey>
  childFolders: ReadonlyMap<FolderKey, number[]>
  childDocuments: ReadonlyMap<FolderKey, WorkspaceDocument[]>
  folderOfDocument: ReadonlyMap<number, FolderKey>
}

function push<K, V>(map: Map<K, V[]>, key: K, value: V) {
  const list = map.get(key)
  if (list) list.push(value)
  else map.set(key, [value])
}

const byName = new Intl.Collator(undefined, { sensitivity: "base" })

export function indexSources(
  folders: SourceFolder[],
  documents: WorkspaceDocument[]
): SourceIndex {
  const roots = new Set(
    folders.flatMap((folder) => (folder.parent_id === null ? [folder.id] : []))
  )
  const shown = new Map(
    folders.flatMap((folder) =>
      roots.has(folder.id) ? [] : [[folder.id, folder] as const]
    )
  )
  const keyOf = (folderId: number | null | undefined): FolderKey =>
    folderId != null && shown.has(folderId) ? folderId : TOP

  const parentOf = new Map<number, FolderKey>()
  const childFolders = new Map<FolderKey, number[]>()
  for (const folder of [...shown.values()].sort((a, b) =>
    byName.compare(a.name, b.name)
  )) {
    const parent = keyOf(folder.parent_id)
    parentOf.set(folder.id, parent)
    push(childFolders, parent, folder.id)
  }

  const childDocuments = new Map<FolderKey, WorkspaceDocument[]>()
  const folderOfDocument = new Map<number, FolderKey>()
  // In the listing's order, newest first, as the flat list showed them.
  for (const document of documents) {
    const folder = keyOf(document.folder_id)
    folderOfDocument.set(document.id, folder)
    push(childDocuments, folder, document)
  }

  return {
    rootFolderId: roots.size > 0 ? [...roots][0] : null,
    folders: shown,
    parentOf,
    childFolders,
    childDocuments,
    folderOfDocument,
  }
}

/** The folder, then its parents up to the top, nearest first. */
export function chainOf(index: SourceIndex, key: FolderKey): number[] {
  const chain: number[] = []
  const seen = new Set<number>()
  let current = key
  while (current !== TOP && !seen.has(current)) {
    seen.add(current)
    chain.push(current)
    current = index.parentOf.get(current) ?? TOP
  }
  return chain
}

/** Every folder under this one, itself included. */
export function subtreeOf(index: SourceIndex, folderId: number): Set<number> {
  const subtree = new Set<number>()
  const pending = [folderId]
  while (pending.length > 0) {
    const next = pending.pop() as number
    if (subtree.has(next)) continue
    subtree.add(next)
    pending.push(...(index.childFolders.get(next) ?? []))
  }
  return subtree
}

/** Every source under this folder, at any depth. */
export function documentsUnder(
  index: SourceIndex,
  folderId: number
): WorkspaceDocument[] {
  return [...subtreeOf(index, folderId)].flatMap(
    (folder) => index.childDocuments.get(folder) ?? []
  )
}

/** Where a new folder or an upload goes when the top level is meant. */
export function folderIdFor(index: SourceIndex, key: FolderKey): number | null {
  return key === TOP ? index.rootFolderId : key
}
