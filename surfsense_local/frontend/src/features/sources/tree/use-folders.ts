import { useCallback, useEffect, useRef, useState } from "react"
import { toast } from "sonner"

import { errorToast } from "@/features/feedback/error-toast"
import { useWorkspaceChanges } from "@/features/workspaces/use-workspace-changes"
import { intl } from "@/i18n/intl"

import {
  createFolder,
  deleteFolder,
  getFolderSummary,
  listFolders,
  moveDocuments,
  updateFolder,
  type FolderSummary,
  type SourceFolder,
} from "./folders-api"

function messageOf(cause: unknown) {
  return cause instanceof Error
    ? cause.message
    : intl.formatMessage({
        id: "sources_folder_unexpected_error",
        defaultMessage: "An unexpected error occurred",
      })
}

/** What the tree asks of its folders; each answers whether it went through. */
export type FolderActions = {
  create: (parentId: number | null, name: string) => Promise<boolean>
  rename: (folderId: number, name: string) => Promise<boolean>
  move: (folderId: number, parentId: number) => Promise<boolean>
  remove: (folderId: number) => Promise<boolean>
  // What a delete would remove; null when the server can't say.
  summarize: (folderId: number) => Promise<FolderSummary | null>
  moveDocuments: (documentIds: number[], folderId: number) => Promise<boolean>
}

/**
 * The workspace's folders, kept fresh by the workspace's folder events.
 * `onSourcesMoved` reloads the sources a delete or a move touched.
 */
export function useFolders(workspaceId: number, onSourcesMoved: () => void) {
  const [folders, setFolders] = useState<SourceFolder[]>([])
  const controller = useRef<AbortController | null>(null)

  const reload = useCallback(() => {
    controller.current?.abort()
    const next = new AbortController()
    controller.current = next
    void listFolders(workspaceId, next.signal)
      .then((listed) => {
        if (controller.current === next) setFolders(listed)
      })
      .catch(() => {
        // The tree keeps what it had; the next event or action reloads.
      })
  }, [workspaceId])

  useEffect(() => {
    reload()
    return () => controller.current?.abort()
  }, [reload])

  useWorkspaceChanges(workspaceId, "folders", reload)

  const attempt = async (
    failure: string,
    action: () => Promise<unknown>
  ): Promise<boolean> => {
    try {
      await action()
      return true
    } catch (cause) {
      errorToast(failure, { description: messageOf(cause) })
      return false
    }
  }

  const actions: FolderActions = {
    create: (parentId, name) =>
      attempt(
        intl.formatMessage({
          id: "sources_folder_create_toast",
          defaultMessage: "Couldn’t create the folder",
        }),
        async () => {
          const created = await createFolder(workspaceId, {
            parent_id: parentId,
            name,
          })
          setFolders((current) => [
            ...current.filter((folder) => folder.id !== created.id),
            created,
          ])
        }
      ),
    rename: (folderId, name) =>
      attempt(
        intl.formatMessage({
          id: "sources_folder_rename_toast",
          defaultMessage: "Couldn’t rename the folder",
        }),
        async () => {
          const renamed = await updateFolder(workspaceId, folderId, { name })
          setFolders((current) =>
            current.map((folder) => (folder.id === folderId ? renamed : folder))
          )
        }
      ),
    move: (folderId, parentId) =>
      attempt(
        intl.formatMessage({
          id: "sources_folder_move_toast",
          defaultMessage: "Couldn’t move the folder",
        }),
        async () => {
          const moved = await updateFolder(workspaceId, folderId, {
            parent_id: parentId,
          })
          setFolders((current) =>
            current.map((folder) => (folder.id === folderId ? moved : folder))
          )
        }
      ),
    remove: (folderId) =>
      attempt(
        intl.formatMessage({
          id: "sources_folder_delete_toast",
          defaultMessage: "Couldn’t delete the folder",
        }),
        async () => {
          await deleteFolder(workspaceId, folderId)
          reload()
          onSourcesMoved()
        }
      ),
    summarize: (folderId) =>
      getFolderSummary(workspaceId, folderId).catch(() => null),
    moveDocuments: (documentIds, folderId) =>
      attempt(
        intl.formatMessage(
          {
            id: "sources_documents_move_toast",
            defaultMessage:
              "{count, plural, one {Couldn’t move the source} other {Couldn’t move the sources}}",
          },
          { count: documentIds.length }
        ),
        async () => {
          const outcome = await moveDocuments(
            workspaceId,
            documentIds,
            folderId
          )
          onSourcesMoved()
          if (outcome.skipped.length > 0) {
            toast.info(
              intl.formatMessage(
                {
                  id: "sources_documents_move_skipped_toast",
                  defaultMessage:
                    "{count, plural, one {# source was already in that folder} other {# sources were already in that folder}}",
                },
                { count: outcome.skipped.length }
              )
            )
          }
        }
      ),
  }

  return { folders, reload, actions }
}
