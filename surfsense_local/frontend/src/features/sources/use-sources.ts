import { useEffect, useRef, useState } from "react"

import {
  listDocuments,
  readDocument,
  retryDocument,
  type DocumentDetail,
  type WorkspaceDocument,
} from "./api"

function isAbort(error: unknown) {
  return error instanceof DOMException && error.name === "AbortError"
}

function messageFrom(error: unknown) {
  return error instanceof Error ? error.message : "An unexpected error occurred"
}

export function useSources(workspaceId: number) {
  const [documents, setDocuments] = useState<WorkspaceDocument[]>([])
  const [selectedDocument, setSelectedDocument] =
    useState<DocumentDetail | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [isLoadingPreview, setIsLoadingPreview] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const listController = useRef<AbortController | null>(null)
  const detailController = useRef<AbortController | null>(null)

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
    }
  }, [workspaceId])

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

  return {
    documents,
    selectedDocument,
    isLoading,
    isLoadingPreview,
    error,
    refresh,
    openDocument,
    closePreview: () => {
      detailController.current?.abort()
      setSelectedDocument(null)
      setIsLoadingPreview(false)
    },
    retry,
  }
}
