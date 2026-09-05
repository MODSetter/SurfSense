import { useEffect, useRef, useState } from "react"

import {
  listDocuments,
  readDocument,
  retryDocument,
  uploadDocuments,
  type DocumentDetail,
  type UploadOutcome,
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
  const [selectedDocument, setSelectedDocument] =
    useState<DocumentDetail | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [isLoadingPreview, setIsLoadingPreview] = useState(false)
  const [isUploading, setIsUploading] = useState(false)
  const [uploadOutcome, setUploadOutcome] = useState<UploadOutcome | null>(null)
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
    uploadController.current?.abort()
    const controller = new AbortController()
    uploadController.current = controller
    setIsUploading(true)
    setUploadOutcome(null)
    setError(null)
    try {
      const outcome = await uploadDocuments(
        workspaceId,
        files,
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
      setUploadOutcome(outcome)
    } catch (cause) {
      if (!isAbort(cause) && uploadController.current === controller) {
        setError(messageFrom(cause))
      }
    } finally {
      if (uploadController.current === controller) {
        setIsUploading(false)
      }
    }
  }

  return {
    documents,
    selectedDocument,
    isLoading,
    isLoadingPreview,
    isUploading,
    uploadOutcome,
    error,
    refresh,
    openDocument,
    closePreview: () => {
      detailController.current?.abort()
      setSelectedDocument(null)
      setIsLoadingPreview(false)
    },
    retry,
    upload,
    dismissUploadOutcome: () => setUploadOutcome(null),
  }
}
