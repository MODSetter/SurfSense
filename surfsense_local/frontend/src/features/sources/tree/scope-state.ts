import { TOP, chainOf, type FolderKey, type SourceIndex } from "./source-index"

/**
 * What the server resolves into a turn's or a job's sources. A ticked folder is
 * dynamic: a file added to it later is in scope. Mirrors the API's SourceScope.
 */
export type SourceScope = {
  all: boolean
  folder_ids: number[]
  excluded_folder_ids: number[]
  document_ids: number[]
  excluded_document_ids: number[]
}

/**
 * The user's ticks. The nearest mark up the tree decides, and `all` decides
 * where none does, so ticking a folder ticks everything under it.
 */
export type ScopeMarks = {
  all: boolean
  folders: ReadonlyMap<number, boolean>
  documents: ReadonlyMap<number, boolean>
}

export type Tick = "checked" | "unchecked" | "mixed"

export function everySource(all: boolean): ScopeMarks {
  return { all, folders: new Map(), documents: new Map() }
}

function folderMarked(marks: ScopeMarks, index: SourceIndex, key: FolderKey) {
  for (const folder of chainOf(index, key)) {
    const mark = marks.folders.get(folder)
    if (mark !== undefined) return mark
  }
  return marks.all
}

export function isDocumentIncluded(
  marks: ScopeMarks,
  index: SourceIndex,
  documentId: number
): boolean {
  return (
    marks.documents.get(documentId) ??
    folderMarked(marks, index, index.folderOfDocument.get(documentId) ?? TOP)
  )
}

/** Ticks or unticks one row, and everything under it with a folder. */
export function markIncluded(
  marks: ScopeMarks,
  index: SourceIndex,
  target: { kind: "folder" | "document"; id: number },
  included: boolean
): ScopeMarks {
  const folders = new Map(marks.folders)
  const documents = new Map(marks.documents)
  if (target.kind === "document") {
    documents.delete(target.id)
    const inherited = folderMarked(
      { ...marks, folders },
      index,
      index.folderOfDocument.get(target.id) ?? TOP
    )
    if (inherited !== included) documents.set(target.id, included)
    return { all: marks.all, folders, documents }
  }
  const under = new Set<number>()
  const pending = [target.id]
  while (pending.length > 0) {
    const folder = pending.pop() as number
    if (under.has(folder)) continue
    under.add(folder)
    folders.delete(folder)
    pending.push(...(index.childFolders.get(folder) ?? []))
    for (const document of index.childDocuments.get(folder) ?? []) {
      documents.delete(document.id)
    }
  }
  const inherited = folderMarked(
    { ...marks, folders },
    index,
    index.parentOf.get(target.id) ?? TOP
  )
  if (inherited !== included) folders.set(target.id, included)
  return { all: marks.all, folders, documents }
}

type Summary = { anyIn: boolean; anyOut: boolean }

/** Each folder's tick, and the top level's under `TOP`'s key, `-1`. */
export function ticksOf(
  marks: ScopeMarks,
  index: SourceIndex
): Map<number, Tick> {
  const ticks = new Map<number, Tick>()
  const visit = (key: FolderKey, included: boolean): Summary => {
    const summary: Summary = { anyIn: false, anyOut: false }
    let empty = true
    for (const document of index.childDocuments.get(key) ?? []) {
      empty = false
      if (marks.documents.get(document.id) ?? included) summary.anyIn = true
      else summary.anyOut = true
    }
    for (const child of index.childFolders.get(key) ?? []) {
      empty = false
      const inner = visit(child, marks.folders.get(child) ?? included)
      summary.anyIn ||= inner.anyIn
      summary.anyOut ||= inner.anyOut
    }
    if (empty) {
      summary.anyIn = included
      summary.anyOut = !included
    }
    ticks.set(
      key ?? -1,
      summary.anyIn && summary.anyOut
        ? "mixed"
        : summary.anyIn
          ? "checked"
          : "unchecked"
    )
    return summary
  }
  visit(TOP, marks.all)
  return ticks
}

function anyFolderTickedUnder(
  marks: ScopeMarks,
  index: SourceIndex,
  folderId: number
): boolean {
  const pending = [folderId]
  while (pending.length > 0) {
    const folder = pending.pop() as number
    for (const child of index.childFolders.get(folder) ?? []) {
      if (marks.folders.get(child) === true) return true
      pending.push(child)
    }
  }
  return false
}

/**
 * The ticks as the server's scope. The server takes `all` and ticked folders,
 * removes excluded folders, then adds and removes single sources. A ticked
 * source inside an unticked folder is added back, so the folder stays excluded
 * whole and a file added to it later stays out; only a ticked subfolder can't
 * be added back, so such a folder's rows are excluded one by one instead.
 */
export function scopeOf(marks: ScopeMarks, index: SourceIndex): SourceScope {
  const scope: SourceScope = {
    all: marks.all,
    folder_ids: [],
    excluded_folder_ids: [],
    document_ids: [],
    excluded_document_ids: [],
  }
  const walk = (key: FolderKey, servedIn: boolean, included: boolean) => {
    for (const document of index.childDocuments.get(key) ?? []) {
      const wanted = marks.documents.get(document.id) ?? included
      if (wanted && !servedIn) scope.document_ids.push(document.id)
      if (!wanted && servedIn) scope.excluded_document_ids.push(document.id)
    }
    for (const child of index.childFolders.get(key) ?? []) {
      const wanted = marks.folders.get(child) ?? included
      let served = servedIn
      if (wanted && !servedIn) {
        scope.folder_ids.push(child)
        served = true
      } else if (
        !wanted &&
        servedIn &&
        !anyFolderTickedUnder(marks, index, child)
      ) {
        scope.excluded_folder_ids.push(child)
        served = false
      }
      walk(child, served, wanted)
    }
  }
  walk(TOP, marks.all, marks.all)
  return scope
}
