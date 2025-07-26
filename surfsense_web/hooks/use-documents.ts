"use client";
import { useState, useEffect, useCallback } from "react";
import { toast } from "sonner";

export interface Document {
  id: number;
  title: string;
  document_type: DocumentType;
  document_metadata: any;
  content: string;
  created_at: string;
  search_space_id: number;
}

export type DocumentType =
  | "EXTENSION"
  | "CRAWLED_URL"
  | "SLACK_CONNECTOR"
  | "NOTION_CONNECTOR"
  | "FILE"
  | "YOUTUBE_VIDEO"
  | "GITHUB_CONNECTOR"
  | "LINEAR_CONNECTOR"
  | "DISCORD_CONNECTOR"
  | "JIRA_CONNECTOR";

export function useDocuments(searchSpaceId: number, lazy: boolean = false) {
  const [documents, setDocuments] = useState<Document[]>([]);
  const [loading, setLoading] = useState(!lazy); // Don't show loading initially for lazy mode
  const [error, setError] = useState<string | null>(null);
  const [isLoaded, setIsLoaded] = useState(false); // Memoization flag

  const fetchDocuments = useCallback(async () => {
    if (isLoaded && lazy) return; // Avoid redundant calls in lazy mode

    try {
      setLoading(true);
      const response = await fetch(
        `${process.env.NEXT_PUBLIC_FASTAPI_BACKEND_URL}/api/v1/documents?search_space_id=${searchSpaceId}`,
        {
          headers: {
            Authorization: `Bearer ${localStorage.getItem(
              "surfsense_bearer_token",
            )}`,
          },
          method: "GET",
        },
      );

      if (!response.ok) {
        toast.error("Failed to fetch documents");
        throw new Error("Failed to fetch documents");
      }

      const data = await response.json();
      setDocuments(data);
      setError(null);
      setIsLoaded(true);
    } catch (err: any) {
      setError(err.message || "Failed to fetch documents");
      console.error("Error fetching documents:", err);
    } finally {
      setLoading(false);
    }
  }, [searchSpaceId, isLoaded, lazy]);

  useEffect(() => {
    if (!lazy && searchSpaceId) {
      fetchDocuments();
    }
  }, [searchSpaceId, lazy, fetchDocuments]);

  // Function to refresh the documents list
  const refreshDocuments = useCallback(async () => {
    setIsLoaded(false); // Reset memoization flag to allow refetch
    await fetchDocuments();
  }, [fetchDocuments]);

  // Function to delete a document
  const deleteDocument = useCallback(
    async (documentId: number) => {
      try {
        const response = await fetch(
          `${process.env.NEXT_PUBLIC_FASTAPI_BACKEND_URL}/api/v1/documents/${documentId}`,
          {
            headers: {
              Authorization: `Bearer ${localStorage.getItem(
                "surfsense_bearer_token",
              )}`,
            },
            method: "DELETE",
          },
        );

        if (!response.ok) {
          toast.error("Failed to delete document");
          throw new Error("Failed to delete document");
        }

        toast.success("Document deleted successfully");
        // Update the local state after successful deletion
        setDocuments(documents.filter((doc) => doc.id !== documentId));
        return true;
      } catch (err: any) {
        toast.error(err.message || "Failed to delete document");
        console.error("Error deleting document:", err);
        return false;
      }
    },
    [documents],
  );

  return {
    documents,
    loading,
    error,
    isLoaded,
    fetchDocuments, // Manual fetch function for lazy mode
    refreshDocuments,
    deleteDocument,
  };
}
