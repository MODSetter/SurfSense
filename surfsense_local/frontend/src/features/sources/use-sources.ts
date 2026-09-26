import { useEffect, useRef, useState } from "react"
import { toast } from "sonner"

import { errorToast } from "@/features/feedback/error-toast"
import { intl } from "@/i18n/intl"

import {
  cancelDocument,
  deleteDocument,
  isSupportedSourceFile,
  listDocuments,
  retryDocument,
  uploadDocuments,
  type WorkspaceDocument,
} from "./api"

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

function readyIdsOf(documents: WorkspaceDocument[]) {
  return documents.flatMap((document) =>
    document.status === "ready" ? [document.id] : []
  )
}

export function useSources(workspaceId: number) {
  const [documents, setDocuments] = useState<WorkspaceDocument[]>([])
  const [selectedDocumentIdSet, setSelectedDocumentIdSet] = useState(
    () => new Set<number>()
  )
  const [excludedDocumentIdSet, setExcludedDocumentIdSet] = useState(
    () => new Set<number>()
  )
  const [isLoading, setIsLoading] = useState(true)
  const [isUploading, setIsUploading] = useState(false)
  const [isDeleting, setIsDeleting] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const listController = useRef<AbortController | null>(null)
  const uploadController = useRef<AbortController | null>(null)
  const pollController = useRef<AbortController | null>(null)
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
          setDocuments(next)
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
          await wait(1500, controller.signal)
          const next = await listDocuments(workspaceId, controller.signal)
          if (pollController.current !== controller) {
            return
          }
          setDocuments(next)
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

  const refresh = async () => {
    listController.current?.abort()
    const controller = new AbortController()
    listController.current = controller
    setIsLoading(true)
    try {
      const next = await listDocuments(workspaceId, controller.signal)
      if (listController.current === controller) {
        setDocuments(next)
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
  }

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

  const openOriginal = (documentId: number) => {
    const bridge = window.surfsense
    return runNativeDocumentAction(
      intl.formatMessage({
        id: "sources_open_original_error",
        defaultMessage: "Couldn’t open source",
      }),
      bridge ? () => bridge.openDocument(workspaceId, documentId) : undefined
    )
  }

  const revealOriginal = (documentId: number) => {
    const bridge = window.surfsense
    return runNativeDocumentAction(
      intl.formatMessage({
        id: "sources_reveal_original_error",
        defaultMessage: "Couldn’t locate source",
      }),
      bridge ? () => bridge.revealDocument(workspaceId, documentId) : undefined
    )
  }

  const retry = async (documentId: number) => {
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
  }

  const cancel = async (documentId: number) => {
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
  }

  const upload = async (files: File[]) => {
    if (files.length === 0) {
      return
    }
    const supported = files.filter(isSupportedSourceFile)
    const unsupported = files.filter((file) => !isSupportedSourceFile(file))
    if (supported.length === 0) {
      errorToast(
        intl.formatMessage(
          {
            id: "sources_upload_failed_toast",
            defaultMessage:
              "{count, plural, one {Couldn’t add your source} other {Couldn’t add your sources}}",
          },
          { count: files.length }
        ),
        {
          id: "source-upload-error",
          description: intl.formatMessage(
            {
              id: "sources_upload_unsupported_error",
              defaultMessage: "Unsupported file type: {files}",
            },
            {
              files: unsupported.map((file) => file.name).join(", "),
            }
          ),
        }
      )
      return
    }
    uploadController.current?.abort()
    const controller = new AbortController()
    uploadController.current = controller
    setIsUploading(true)
    setError(null)
    try {
      const outcome = await uploadDocuments(
        workspaceId,
        supported,
        controller.signal
      )
      if (uploadController.current !== controller) {
        return
      }
      setDocuments((current) => {
        const createdIds = new Set(
          outcome.created.map((document) => document.id)
        )
        return [
          ...current.filter((document) => !createdIds.has(document.id)),
          ...outcome.created,
        ]
      })
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
      const description = [
        count > 0
          ? intl.formatMessage({
              id: "sources_upload_ingesting_body",
              defaultMessage: "Ingestion is running in the background.",
            })
          : null,
        outcome.duplicates.length > 0
          ? intl.formatMessage(
              {
                id: "sources_upload_duplicates_body",
                defaultMessage: "Already present: {files}",
              },
              {
                files: outcome.duplicates
                  .map((duplicate) => duplicate.filename)
                  .join(", "),
              }
            )
          : null,
        unsupported.length > 0
          ? intl.formatMessage(
              {
                id: "sources_upload_unsupported_body",
                defaultMessage: "Not supported: {files}",
              },
              {
                files: unsupported.map((file) => file.name).join(", "),
              }
            )
          : null,
        outcome.rejected.length > 0
          ? intl.formatMessage(
              {
                id: "sources_upload_rejected_body",
                defaultMessage: "Rejected: {files}",
              },
              {
                files: outcome.rejected
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
        errorToast(
          intl.formatMessage(
            {
              id: "sources_upload_failed_toast",
              defaultMessage:
                "{count, plural, one {Couldn’t add your source} other {Couldn’t add your sources}}",
            },
            { count: files.length }
          ),
          {
            id: "source-upload-error",
            description: messageFrom(cause),
          }
        )
      }
    } finally {
      if (uploadController.current === controller) {
        setIsUploading(false)
      }
    }
  }

  const selectedDocumentIds = documents.flatMap((document) =>
    document.status === "ready" && selectedDocumentIdSet.has(document.id)
      ? [document.id]
      : []
  )
  const includedDocumentIds = documents.flatMap((document) =>
    document.status === "ready" && !excludedDocumentIdSet.has(document.id)
      ? [document.id]
      : []
  )

  const setDocumentSelected = (documentId: number, selected: boolean) => {
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

  const setDocumentIncluded = (documentId: number, included: boolean) => {
    setExcludedDocumentIdSet((current) => {
      const next = new Set(current)
      if (included) {
        next.delete(documentId)
      } else {
        next.add(documentId)
      }
      return next
    })
  }

  const toggleAllIncluded = () => {
    const readyIds = readyIdsOf(documents)
    const allIncluded =
      readyIds.length > 0 &&
      readyIds.every((id) => !excludedDocumentIdSet.has(id))
    setExcludedDocumentIdSet(allIncluded ? new Set(readyIds) : new Set())
  }

  const deleteOne = async (documentId: number) => {
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
  }

  const deleteSelected = async () => {
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
  }

  return {
    documents,
    selectedDocumentIds,
    includedDocumentIds,
    isLoading,
    isUploading,
    isDeleting,
    error,
    refresh,
    openOriginal,
    revealOriginal,
    retry,
    cancel,
    deleteOne,
    deleteSelected,
    setDocumentSelected,
    setDocumentIncluded,
    toggleAllIncluded,
    upload,
  }
}
