"use client"
import { useState, useEffect } from 'react';
import { toast } from 'sonner';

export interface Document {
  id: number;
  title: string;
  document_type: "EXTENSION" | "CRAWLED_URL" | "SLACK_CONNECTOR" | "NOTION_CONNECTOR" | "FILE";
  document_metadata: any;
  content: string;
  created_at: string;
  search_space_id: number;
}

export function useDocuments(searchSpaceId: number) {
  const [documents, setDocuments] = useState<Document[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const fetchDocuments = async () => {
      try {
        setLoading(true);
        const response = await fetch(
          `${process.env.NEXT_PUBLIC_FASTAPI_BACKEND_URL}/api/v1/documents`, 
          {
            headers: {
              Authorization: `Bearer ${localStorage.getItem('surfsense_bearer_token')}`,
            },
            method: "GET",
          }
        );
        
        if (!response.ok) {
          toast.error("Failed to fetch documents");
          throw new Error("Failed to fetch documents");
        }
        
        const data = await response.json();
        setDocuments(data);
        setError(null);
      } catch (err: any) {
        setError(err.message || 'Failed to fetch documents');
        console.error('Error fetching documents:', err);
      } finally {
        setLoading(false);
      }
    };

    if (searchSpaceId) {
      fetchDocuments();
    }
  }, [searchSpaceId]);

  // Function to refresh the documents list
  const refreshDocuments = async () => {
    setLoading(true);
    try {
      const response = await fetch(
        `${process.env.NEXT_PUBLIC_FASTAPI_BACKEND_URL}/api/v1/documents`, 
        {
          headers: {
            Authorization: `Bearer ${localStorage.getItem('surfsense_bearer_token')}`,
          },
          method: "GET",
        }
      );
      
      if (!response.ok) {
        toast.error("Failed to fetch documents");
        throw new Error("Failed to fetch documents");
      }
      
      const data = await response.json();
      setDocuments(data);
      setError(null);
    } catch (err: any) {
      setError(err.message || 'Failed to fetch documents');
      console.error('Error fetching documents:', err);
    } finally {
      setLoading(false);
    }
  };

  // Function to delete a document
  const deleteDocument = async (documentId: number) => {
    try {
      const response = await fetch(
        `${process.env.NEXT_PUBLIC_FASTAPI_BACKEND_URL}/api/v1/documents/${documentId}`,
        {
          headers: {
            Authorization: `Bearer ${localStorage.getItem('surfsense_bearer_token')}`,
          },
          method: "DELETE",
        }
      );

      if (!response.ok) {
        toast.error("Failed to delete document");
        throw new Error("Failed to delete document");
      }

      toast.success("Document deleted successfully");
      // Update the local state after successful deletion
      setDocuments(documents.filter(doc => doc.id !== documentId));
      return true;
    } catch (err: any) {
      toast.error(err.message || 'Failed to delete document');
      console.error('Error deleting document:', err);
      return false;
    }
  };

  return { documents, loading, error, refreshDocuments, deleteDocument };
} 