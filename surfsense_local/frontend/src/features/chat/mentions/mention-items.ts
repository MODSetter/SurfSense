import type { TriggerItem } from "@assistant-ui/react"

import { intl } from "@/i18n/intl"
import type { WorkspaceDocument } from "@/features/sources/api"
import {
  documentsUnder,
  type SourceIndex,
} from "@/features/sources/tree/source-index"
import type { Artifact } from "@/features/studio/api"
import { artifactLines, newestReady } from "@/features/studio/artifact-versions"
import { formatLabel } from "@/features/studio/studio-formats"

/** What the composer's `@` list is built from, all of it already loaded by the page. */
export type Mentionables = {
  documents: WorkspaceDocument[]
  index: SourceIndex
  artifacts: Artifact[]
  isLoading?: boolean
}

export const MENTION_GROUPS = ["source", "artifact"] as const

const isReady = (document: WorkspaceDocument) => document.status === "ready"

function folderItems({ index }: Mentionables): TriggerItem[] {
  return [...index.folders.values()].flatMap((folder) => {
    const count = documentsUnder(index, folder.id).filter(isReady).length
    if (count === 0) return []
    return {
      id: `folder:${folder.id}`,
      type: "source",
      label: folder.name,
      description: intl.formatMessage(
        {
          id: "chat_mentions_folder_files_label",
          defaultMessage: "{count, plural, one {# file} other {# files}}",
        },
        { count }
      ),
    }
  })
}

function fileItems({ documents, index }: Mentionables): TriggerItem[] {
  return documents.filter(isReady).map((document) => {
    const folder = index.folders.get(document.folder_id ?? -1)?.name
    return {
      id: `document:${document.id}`,
      type: "source",
      label: document.title,
      ...(folder === undefined ? {} : { description: folder }),
    }
  })
}

function artifactItems({ artifacts }: Mentionables): TriggerItem[] {
  return artifactLines(artifacts).flatMap(({ versions }) => {
    const ready = newestReady(versions)
    if (!ready) return []
    return {
      id: `document:${ready.document_id}`,
      type: "artifact",
      label: ready.title,
      description: formatLabel({ key: ready.format, label: ready.format }),
      metadata: { format: ready.format },
    }
  })
}

/** Everything `@` can name: only what a turn could read now. */
export function mentionItems(from: Mentionables): TriggerItem[] {
  return [...folderItems(from), ...fileItems(from), ...artifactItems(from)]
}

export const isFolderItem = (item: TriggerItem) => item.id.startsWith("folder:")

/** One group's rows, whole: the list keeps its highlight only while this stays
 *  the same list, so it loads more as it renders rather than by asking again. */
export function mentionsOfGroup(items: readonly TriggerItem[], group: string) {
  return items.filter((item) => item.type === group)
}

/** Every match, sources before artifacts, those starting with the words first in
 *  each. Names only: the detail is a folder or a format, which would match too much. */
export function searchMentions(
  items: readonly TriggerItem[],
  query: string
): TriggerItem[] {
  const words = query.trim().toLowerCase()
  const matches = items.filter((item) =>
    item.label.toLowerCase().includes(words)
  )
  const ranked = [
    ...matches.filter((item) => item.label.toLowerCase().startsWith(words)),
    ...matches.filter((item) => !item.label.toLowerCase().startsWith(words)),
  ]
  return MENTION_GROUPS.flatMap((group) => mentionsOfGroup(ranked, group))
}
