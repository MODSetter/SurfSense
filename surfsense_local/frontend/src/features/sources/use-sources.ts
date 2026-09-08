import { useEffect, useRef, useState } from "react"
import { toast } from "sonner"

import {
  deleteDocument,
  isSupportedSourceFile,
  listDocuments,
  readDocument,
  retryDocument,
  uploadDocuments,
  type DocumentDetail,
  type WorkspaceDocument,
} from "./api"

function isAbort(error: unknown) {
  return error instanceof DOMException && error.name === "AbortError"
}

function messageFrom(error: unknown) {
  return error instanceof Error ? error.message : "An unexpected error occurred"
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
  const [selectedDocument, setSelectedDocument] =
    useState<DocumentDetail | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [isLoadingPreview, setIsLoadingPreview] = useState(false)
  const [isUploading, setIsUploading] = useState(false)
  const [isDeleting, setIsDeleting] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const listController = useRef<AbortController | null>(null)
  const detailController = useRef<AbortController | null>(null)
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
      detailController.current?.abort()
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

  const openDocument = async (documentId: number) => {
    detailController.current?.abort()
    const controller = new AbortController()
    detailController.current = controller
    setIsLoadingPreview(true)
    setError(null)
    try {
      const detail = await readDocument(
        workspaceId,
        documentId,
        controller.signal
      )
      if (detailController.current === controller) {
        setSelectedDocument(detail)
      }
    } catch (cause) {
      if (!isAbort(cause) && detailController.current === controller) {
        setError(messageFrom(cause))
      }
    } finally {
      if (detailController.current === controller) {
        setIsLoadingPreview(false)
      }
    }
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

  const upload = async (files: File[]) => {
    if (files.length === 0) {
      return
    }
    const supported = files.filter(isSupportedSourceFile)
    const unsupported = files.filter((file) => !isSupportedSourceFile(file))
    if (supported.length === 0) {
      toast.error(`Couldn’t add your source${files.length === 1 ? "" : "s"}`, {
        id: "source-upload-error",
        description: `Unsupported file type: ${unsupported
          .map((file) => file.name)
          .join(", ")}`,
      })
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
          ? `${count} source${count === 1 ? "" : "s"} added`
          : "No new sources added"
      const description = [
        count > 0 ? "Ingestion is running in the background." : null,
        outcome.duplicates.length > 0
          ? `Already present: ${outcome.duplicates
              .map((duplicate) => duplicate.filename)
              .join(", ")}`
          : null,
        unsupported.length > 0
          ? `Not supported: ${unsupported.map((file) => file.name).join(", ")}`
          : null,
        outcome.rejected.length > 0
          ? `Rejected: ${outcome.rejected
              .map((rejection) => `${rejection.filename} (${rejection.reason})`)
              .join(", ")}`
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
        toast.error(
          `Couldn’t add your source${files.length === 1 ? "" : "s"}`,
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
        `${failedCount} selected source${failedCount === 1 ? "" : "s"} could not be deleted.`
      )
    }
    setIsDeleting(false)
  }

  return {
    documents,
    selectedDocumentIds,
    selectedDocument,
    isLoading,
    isLoadingPreview,
    isUploading,
    isDeleting,
    error,
    refresh,
    openDocument,
    closePreview: () => {
      detailController.current?.abort()
      setSelectedDocument(null)
      setIsLoadingPreview(false)
    },
    retry,
    deleteSelected,
    setDocumentSelected,
    upload,
  }
}
