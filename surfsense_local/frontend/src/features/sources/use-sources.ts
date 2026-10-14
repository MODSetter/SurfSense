import { useEffect, useMemo, useRef, useState } from "react"
import { toast } from "sonner"

import { errorToast } from "@/features/feedback/error-toast"
import { useWorkspaceChanges } from "@/features/workspaces/use-workspace-changes"
import { useStableCallback } from "@/hooks/use-stable-callback"
import { intl } from "@/i18n/intl"

import {
  cancelDocument,
  createNote,
  deleteDocument,
  getDocument,
  listDocuments,
  retryDocument,
  updateDocument,
  uploadDocuments,
  type UploadOutcome,
  type WorkspaceDocument,
} from "./api"
import {
  MAX_SOURCE_BYTES,
  planUpload,
  type UploadEntry,
} from "./folder-upload/upload-plan"
import { reuseUnchanged } from "./reuse-unchanged"
import { indexSources } from "./tree/source-index"
import { useFolders } from "./tree/use-folders"
import { useSourceScope } from "./tree/use-source-scope"

const MAX_SOURCE_MEGABYTES = MAX_SOURCE_BYTES / 1024 / 1024

// The worker's notices are best-effort: one lost while a row is in flight would
// leave it stale, so the list is still re-read now and then until none is.
const LOST_NOTICE_POLL_MS = 10_000

function isAbort(error: unknown) {
  return error instanceof DOMException && error.name === "AbortError"
}

function messageFrom(error: unknown) {
  return error instanceof Error
    ? error.message
    : intl.formatMessage({
        id: "sources_unexpected_error",
        defaultMessage: "An unexpected error occurred",
      })
}

function wait(milliseconds: number, signal: AbortSignal) {
  return new Promise<void>((resolve, reject) => {
    const onAbort = () => {
      window.clearTimeout(timeout)
      reject(new DOMException("Aborted", "AbortError"))
    }
    const timeout = window.setTimeout(() => {
      signal.removeEventListener("abort", onAbort)
      resolve()
    }, milliseconds)
    signal.addEventListener("abort", onAbort, { once: true })
  })
}

export function useSources(workspaceId: number) {
  const [documents, setDocuments] = useState<WorkspaceDocument[]>([])
  const [selectedDocumentIdSet, setSelectedDocumentIdSet] = useState(
    () => new Set<number>()
  )
  const [isLoading, setIsLoading] = useState(true)
  const [isUploading, setIsUploading] = useState(false)
  const [isDeleting, setIsDeleting] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const listController = useRef<AbortController | null>(null)
  const uploadController = useRef<AbortController | null>(null)
  const pollController = useRef<AbortController | null>(null)
  const changeController = useRef<AbortController | null>(null)
  const hasActiveIngestion = documents.some(
    (document) =>
      document.status === "pending" || document.status === "processing"
  )

  useEffect(() => {
    const controller = new AbortController()
    listController.current = controller
    void listDocuments(workspaceId, controller.signal)
      .then((next) => {
        if (listController.current === controller) {
          setDocuments((current) => reuseUnchanged(current, next))
          setError(null)
          setIsLoading(false)
        }
      })
      .catch((cause: unknown) => {
        if (!isAbort(cause) && listController.current === controller) {
          setError(messageFrom(cause))
          setIsLoading(false)
        }
      })
    return () => {
      controller.abort()
      uploadController.current?.abort()
      pollController.current?.abort()
      changeController.current?.abort()
    }
  }, [workspaceId])

  useEffect(() => {
    if (!hasActiveIngestion) {
      return
    }
    const controller = new AbortController()
    pollController.current?.abort()
    pollController.current = controller

    void (async () => {
      try {
        while (!controller.signal.aborted) {
          await wait(LOST_NOTICE_POLL_MS, controller.signal)
          const next = await listDocuments(workspaceId, controller.signal)
          if (pollController.current !== controller) {
            return
          }
          setDocuments((current) => reuseUnchanged(current, next))
          setError(null)
          if (
            !next.some(
              (document) =>
                document.status === "pending" ||
                document.status === "processing"
            )
          ) {
            return
          }
        }
      } catch (cause) {
        if (!isAbort(cause) && pollController.current === controller) {
          setError(messageFrom(cause))
        }
      }
    })()

    return () => controller.abort()
  }, [hasActiveIngestion, workspaceId])

  // Without the loading state: the list is on screen, and only its rows move.
  const reloadQuietly = useStableCallback(() => {
    changeController.current?.abort()
    const controller = new AbortController()
    changeController.current = controller
    void listDocuments(workspaceId, controller.signal)
      .then((next) => {
        if (changeController.current === controller) {
          setDocuments((current) => reuseUnchanged(current, next))
          setError(null)
        }
      })
      .catch(() => {
        // The next change, or the re-read while something ingests, reloads.
      })
  })
  useWorkspaceChanges(workspaceId, "documents", reloadQuietly)

  const folders = useFolders(workspaceId, reloadQuietly)
  const index = useMemo(
    () => indexSources(folders.folders, documents),
    [documents, folders.folders]
  )
  const scope = useSourceScope(index, documents)

  const refresh = useStableCallback(async () => {
    listController.current?.abort()
    const controller = new AbortController()
    listController.current = controller
    setIsLoading(true)
    try {
      const next = await listDocuments(workspaceId, controller.signal)
      if (listController.current === controller) {
        setDocuments((current) => reuseUnchanged(current, next))
        setError(null)
      }
    } catch (cause) {
      if (!isAbort(cause) && listController.current === controller) {
        setError(messageFrom(cause))
      }
    } finally {
      if (listController.current === controller) {
        setIsLoading(false)
      }
    }
  })

  const runNativeDocumentAction = async (
    title: string,
    action: (() => Promise<string>) | undefined
  ) => {
    try {
      const error = action
        ? await action()
        : intl.formatMessage({
            id: "sources_native_access_unavailable_error",
            defaultMessage: "Native file access is unavailable.",
          })
      if (error) throw new Error(error)
    } catch (cause) {
      errorToast(title, { description: messageFrom(cause) })
    }
  }

  const openOriginal = useStableCallback((documentId: number) => {
    const bridge = window.surfsense
    return runNativeDocumentAction(
      intl.formatMessage({
        id: "sources_open_original_error",
        defaultMessage: "Couldn’t open source",
      }),
      bridge ? () => bridge.openDocument(workspaceId, documentId) : undefined
    )
  })

  const revealOriginal = useStableCallback((documentId: number) => {
    const bridge = window.surfsense
    return runNativeDocumentAction(
      intl.formatMessage({
        id: "sources_reveal_original_error",
        defaultMessage: "Couldn’t locate source",
      }),
      bridge ? () => bridge.revealDocument(workspaceId, documentId) : undefined
    )
  })

  const retry = useStableCallback(async (documentId: number) => {
    setError(null)
    try {
      const updated = await retryDocument(workspaceId, documentId)
      setDocuments((current) =>
        current.map((document) =>
          document.id === documentId ? updated : document
        )
      )
    } catch (cause) {
      setError(messageFrom(cause))
    }
  })

  const cancel = useStableCallback(async (documentId: number) => {
    setError(null)
    try {
      const updated = await cancelDocument(workspaceId, documentId)
      setDocuments((current) =>
        current.map((document) =>
          document.id === documentId ? updated : document
        )
      )
    } catch (cause) {
      setError(messageFrom(cause))
    }
  })

  const replace = (updated: WorkspaceDocument) =>
    setDocuments((current) =>
      current.map((document) =>
        document.id === updated.id ? updated : document
      )
    )

  // Each answers whether it saved, so its dialog closes only then, and says why
  // not in a toast: the panel's alert sits behind the dialog. An edited note
  // comes back pending, and the ingestion poll carries it to ready.
  const noteFailed = (cause: unknown) =>
    errorToast(
      intl.formatMessage({
        id: "sources_note_save_toast",
        defaultMessage: "Couldn’t save the note",
      }),
      { description: messageFrom(cause) }
    )

  const writeNote = useStableCallback(
    async (title: string, content: string) => {
      try {
        const created = await createNote(workspaceId, { title, content })
        // The server announces the note before it answers, so a refetch may
        // already hold it.
        setDocuments((current) => [
          created,
          ...current.filter((document) => document.id !== created.id),
        ])
        return true
      } catch (cause) {
        noteFailed(cause)
        return false
      }
    }
  )

  const rename = useStableCallback(
    async (documentId: number, title: string) => {
      try {
        replace(await updateDocument(workspaceId, documentId, { title }))
        return true
      } catch (cause) {
        errorToast(
          intl.formatMessage({
            id: "sources_rename_toast",
            defaultMessage: "Couldn’t rename the source",
          }),
          { description: messageFrom(cause) }
        )
        return false
      }
    }
  )

  // Content only when it changed: sending it re-ingests the note.
  const editNote = useStableCallback(
    async (documentId: number, title: string, content?: string) => {
      try {
        replace(
          await updateDocument(
            workspaceId,
            documentId,
            content === undefined ? { title } : { title, content }
          )
        )
        return true
      } catch (cause) {
        noteFailed(cause)
        return false
      }
    }
  )

  const loadNote = useStableCallback(async (documentId: number) => {
    const document = await getDocument(workspaceId, documentId)
    return { title: document.title, content: document.content ?? "" }
  })

  const uploadFailed = (count: number, description: string) =>
    errorToast(
      intl.formatMessage(
        {
          id: "sources_upload_failed_toast",
          defaultMessage:
            "{count, plural, one {Couldn’t add your source} other {Couldn’t add your sources}}",
        },
        { count }
      ),
      { id: "source-upload-error", description }
    )

  /**
   * Adds files, or a folder's files with their paths, under `folderId` (the
   * top level when null). A folder goes up in several requests.
   */
  const uploadEntries = useStableCallback(
    async (entries: UploadEntry[], folderId: number | null = null) => {
      if (entries.length === 0) {
        return
      }
      const fromFolder = entries.some((entry) => entry.relativePath !== null)
      const plan = planUpload(entries)
      const unsupportedNames = plan.unsupported.map((file) => file.name)
      if (plan.batches.length === 0) {
        uploadFailed(
          entries.length,
          plan.tooLarge.length > 0
            ? intl.formatMessage(
                {
                  id: "sources_upload_too_large_error",
                  defaultMessage:
                    "Over {size, number, ::unit/megabyte}: {files}",
                },
                {
                  size: MAX_SOURCE_MEGABYTES,
                  files: plan.tooLarge.map((file) => file.name).join(", "),
                }
              )
            : intl.formatMessage(
                {
                  id: "sources_upload_unsupported_error",
                  defaultMessage: "Unsupported file type: {files}",
                },
                { files: unsupportedNames.join(", ") }
              )
        )
        return
      }
      uploadController.current?.abort()
      const controller = new AbortController()
      uploadController.current = controller
      setIsUploading(true)
      setError(null)
      const outcome: UploadOutcome = {
        created: [],
        duplicates: [],
        rejected: [],
      }
      try {
        for (const batch of plan.batches) {
          const answered = await uploadDocuments(
            workspaceId,
            batch.files,
            controller.signal,
            { folderId, relativePaths: batch.relativePaths }
          )
          if (uploadController.current !== controller) {
            return
          }
          outcome.created.push(...answered.created)
          outcome.duplicates.push(...answered.duplicates)
          outcome.rejected.push(...answered.rejected)
          setDocuments((current) => {
            const createdIds = new Set(
              answered.created.map((document) => document.id)
            )
            // In the server's order, newest first, so the next refetch moves nothing.
            return [
              ...[...answered.created].reverse(),
              ...current.filter((document) => !createdIds.has(document.id)),
            ]
          })
          // A folder's paths made folders on the server.
          if (batch.relativePaths) folders.reload()
        }
        const count = outcome.created.length
        const title =
          count > 0
            ? intl.formatMessage(
                {
                  id: "sources_upload_added_toast",
                  defaultMessage:
                    "{count, plural, one {# source added} other {# sources added}}",
                },
                { count }
              )
            : intl.formatMessage({
                id: "sources_upload_none_added_toast",
                defaultMessage: "No new sources added",
              })
        const rejected = [
          ...plan.tooLarge.map((file) => ({
            filename: file.name,
            reason: intl.formatMessage(
              {
                id: "sources_upload_too_large_reason_label",
                defaultMessage: "Over {size, number, ::unit/megabyte}",
              },
              { size: MAX_SOURCE_MEGABYTES }
            ),
          })),
          ...outcome.rejected,
        ]
        const description = [
          count > 0
            ? intl.formatMessage({
                id: "sources_upload_ingesting_body",
                defaultMessage: "Ingestion is running in the background.",
              })
            : null,
          outcome.duplicates.length === 0
            ? null
            : fromFolder
              ? intl.formatMessage(
                  {
                    id: "sources_upload_folder_duplicates_body",
                    defaultMessage:
                      "{count, plural, one {# file was already in its folder.} other {# files were already in their folders.}}",
                  },
                  { count: outcome.duplicates.length }
                )
              : intl.formatMessage(
                  {
                    id: "sources_upload_duplicates_body",
                    defaultMessage: "Already present: {files}",
                  },
                  {
                    files: outcome.duplicates
                      .map((duplicate) => duplicate.filename)
                      .join(", "),
                  }
                ),
          unsupportedNames.length === 0
            ? null
            : fromFolder
              ? intl.formatMessage(
                  {
                    id: "sources_upload_folder_unsupported_body",
                    defaultMessage:
                      "{count, plural, one {Skipped # file of a type SurfSense can’t read.} other {Skipped # files of types SurfSense can’t read.}}",
                  },
                  { count: unsupportedNames.length }
                )
              : intl.formatMessage(
                  {
                    id: "sources_upload_unsupported_body",
                    defaultMessage: "Not supported: {files}",
                  },
                  { files: unsupportedNames.join(", ") }
                ),
          rejected.length > 0
            ? intl.formatMessage(
                {
                  id: "sources_upload_rejected_body",
                  defaultMessage: "Rejected: {files}",
                },
                {
                  files: rejected
                    .map((rejection) =>
                      intl.formatMessage(
                        {
                          id: "sources_upload_rejected_file_label",
                          defaultMessage: "{filename} ({reason})",
                        },
                        {
                          filename: rejection.filename,
                          reason: rejection.reason,
                        }
                      )
                    )
                    .join(", "),
                }
              )
            : null,
        ]
          .filter(Boolean)
          .join(" ")
        const options = {
          id: "source-upload-outcome",
          description: description || undefined,
        }
        if (count > 0) {
          toast.success(title, options)
        } else {
          toast.info(title, options)
        }
      } catch (cause) {
        if (!isAbort(cause) && uploadController.current === controller) {
          if (outcome.created.length > 0) folders.reload()
          uploadFailed(entries.length, messageFrom(cause))
        }
      } finally {
        if (uploadController.current === controller) {
          setIsUploading(false)
        }
      }
    }
  )

  const upload = useStableCallback(
    (files: File[], folderId: number | null = null) =>
      uploadEntries(
        files.map((file) => ({ file, relativePath: null })),
        folderId
      )
  )

  const selectedDocumentIds = useMemo(
    () =>
      documents.flatMap((document) =>
        document.status === "ready" && selectedDocumentIdSet.has(document.id)
          ? [document.id]
          : []
      ),
    [documents, selectedDocumentIdSet]
  )

  const setDocumentSelected = useStableCallback(
    (documentId: number, selected: boolean) => {
      setSelectedDocumentIdSet((current) => {
        const next = new Set(current)
        if (selected) {
          next.add(documentId)
        } else {
          next.delete(documentId)
        }
        return next
      })
    }
  )

  const deleteOne = useStableCallback(async (documentId: number) => {
    if (isDeleting) {
      return
    }
    setIsDeleting(true)
    setError(null)
    try {
      await deleteDocument(workspaceId, documentId)
      setDocuments((current) =>
        current.filter((document) => document.id !== documentId)
      )
      setSelectedDocumentIdSet((current) => {
        const next = new Set(current)
        next.delete(documentId)
        return next
      })
    } catch (cause) {
      setError(messageFrom(cause))
    } finally {
      setIsDeleting(false)
    }
  })

  const deleteSelected = useStableCallback(async () => {
    const ids = selectedDocumentIds
    if (ids.length === 0 || isDeleting) {
      return
    }
    setIsDeleting(true)
    setError(null)
    const results = await Promise.allSettled(
      ids.map((documentId) => deleteDocument(workspaceId, documentId))
    )
    const deletedIds = new Set(
      ids.filter((_id, index) => results[index].status === "fulfilled")
    )
    setDocuments((current) =>
      current.filter((document) => !deletedIds.has(document.id))
    )
    setSelectedDocumentIdSet((current) => {
      const next = new Set(current)
      for (const id of deletedIds) {
        next.delete(id)
      }
      return next
    })
    const failedCount = results.length - deletedIds.size
    if (failedCount > 0) {
      setError(
        intl.formatMessage(
          {
            id: "sources_delete_selected_error",
            defaultMessage:
              "{count, plural, one {# selected source could not be deleted.} other {# selected sources could not be deleted.}}",
          },
          { count: failedCount }
        )
      )
    }
    setIsDeleting(false)
  })

  return {
    documents,
    folders: folders.folders,
    folderActions: folders.actions,
    index,
    selectedDocumentIds,
    includedDocumentIds: scope.includedDocumentIds,
    sourceScope: scope.scope,
    folderTicks: scope.ticks,
    isLoading,
    isUploading,
    isDeleting,
    error,
    refresh,
    openOriginal,
    revealOriginal,
    retry,
    cancel,
    rename,
    writeNote,
    editNote,
    loadNote,
    deleteOne,
    deleteSelected,
    setDocumentSelected,
    setDocumentIncluded: scope.setDocumentIncluded,
    setFolderIncluded: scope.setFolderIncluded,
    toggleAllIncluded: scope.toggleAllIncluded,
    upload,
    uploadEntries,
  }
}
