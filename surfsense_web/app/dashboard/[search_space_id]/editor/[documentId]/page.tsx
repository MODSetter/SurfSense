"use client";

import { useParams, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { BlockNoteEditor } from "@/components/DynamicBlockNoteEditor";

interface EditorContent {
  document_id: number;
  title: string;
  blocknote_document: any;
  last_edited_at: string | null;
}

export default function EditorPage() {
  const params = useParams();
  const router = useRouter();
  const documentId = params.documentId as string;
  
  const [document, setDocument] = useState<EditorContent | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [editorContent, setEditorContent] = useState<any>(null);
  const [error, setError] = useState<string | null>(null);
  
  // Get auth token
  const token = typeof window !== "undefined" 
    ? localStorage.getItem("surfsense_bearer_token") 
    : null;
  
  // Fetch document content - DIRECT CALL TO FASTAPI
  useEffect(() => {
    async function fetchDocument() {
      if (!token) {
        console.error("No auth token found");
        setError("Please login to access the editor");
        setLoading(false);
        return;
      }
      
      try {
        const response = await fetch(
          `${process.env.NEXT_PUBLIC_FASTAPI_BACKEND_URL}/api/v1/documents/${documentId}/editor-content`,
          {
            headers: {
              Authorization: `Bearer ${token}`,
            },
          }
        );
        
        if (!response.ok) {
          const errorData = await response.json().catch(() => ({ detail: "Failed to fetch document" }));
          throw new Error(errorData.detail || "Failed to fetch document");
        }
        
        const data = await response.json();
        
        // Check if blocknote_document exists
        if (!data.blocknote_document) {
          setError("This document does not have BlockNote content. Please re-upload the document to enable editing.");
          setLoading(false);
          return;
        }
        
        setDocument(data);
        setEditorContent(data.blocknote_document);
        setError(null);
      } catch (error) {
        console.error("Error fetching document:", error);
        setError(error instanceof Error ? error.message : "Failed to fetch document. Please try again.");
      } finally {
        setLoading(false);
      }
    }
    
    if (documentId && token) {
      fetchDocument();
    }
  }, [documentId, token]);
  
  // Auto-save every 30 seconds - DIRECT CALL TO FASTAPI
  useEffect(() => {
    if (!editorContent || !token) return;
    
    const interval = setInterval(async () => {
      try {
        await fetch(
          `${process.env.NEXT_PUBLIC_FASTAPI_BACKEND_URL}/api/v1/documents/${documentId}/blocknote-content`,
          {
            method: "PUT",
            headers: {
              "Content-Type": "application/json",
              Authorization: `Bearer ${token}`,
            },
            body: JSON.stringify({ blocknote_document: editorContent }),
          }
        );
        console.log("Auto-saved");
      } catch (error) {
        console.error("Auto-save failed:", error);
      }
    }, 30000); // 30 seconds
    
    return () => clearInterval(interval);
  }, [editorContent, documentId, token]);
  
  // Save and exit - DIRECT CALL TO FASTAPI
  const handleSave = async () => {
    if (!token) {
      alert("Please login to save");
      return;
    }
    
    if (!editorContent) {
      alert("No content to save");
      return;
    }
    
    setSaving(true);
    try {
      // Save blocknote_document to database (without finalizing/reindexing)
      const response = await fetch(
        `${process.env.NEXT_PUBLIC_FASTAPI_BACKEND_URL}/api/v1/documents/${documentId}/blocknote-content`,
        {
          method: "PUT",
          headers: {
            "Content-Type": "application/json",
            Authorization: `Bearer ${token}`,
          },
          body: JSON.stringify({ blocknote_document: editorContent }),
        }
      );
      
      if (!response.ok) {
        const errorData = await response.json().catch(() => ({ detail: "Failed to save document" }));
        throw new Error(errorData.detail || "Failed to save document");
      }
      
      // Redirect back to documents list
      router.push(`/dashboard/${params.search_space_id}/documents`);
    } catch (error) {
      console.error("Error saving document:", error);
      alert(error instanceof Error ? error.message : "Failed to save document. Please try again.");
    } finally {
      setSaving(false);
    }
  };
  
  if (loading) {
    return <div>Loading editor...</div>;
  }
  
  if (error) {
    return (
      // <div className="h-screen flex items-center justify-center">
      <div className="flex items-center justify-center min-h-[400px]">
        <div className="max-w-md p-6 border border-red-300 rounded-lg bg-red-50">
          <h2 className="text-xl font-bold text-red-800 mb-2">Error</h2>
          <p className="text-red-700 mb-4">{error}</p>
          <button
            type="button"
            onClick={() => router.back()}
            className="px-4 py-2 bg-red-600 text-white rounded hover:bg-red-700"
          >
            Go Back
          </button>
        </div>
      </div>
    );
  }
  
  if (!document) {
    return <div>Document not found</div>;
  }
  
  return (
    // <div className="h-screen flex flex-col">
    <div className="flex flex-col h-full">
      {/* Toolbar */}
      <div className="border-b p-4 flex justify-between items-center">
        <h1 className="text-xl font-bold">{document.title}</h1>
        <div className="flex gap-2">
          <button
            type="button"
            onClick={() => router.back()}
            className="px-4 py-2 border rounded"
          >
            Cancel
          </button>
          <button
            type="button"
            onClick={handleSave}
            disabled={saving}
            className="px-4 py-2 bg-blue-600 text-white rounded disabled:opacity-50"
          >
            {saving ? "Saving..." : "Save & Exit"}
          </button>
        </div>
      </div>
      
      {/* Editor - Now using dynamic import */}
      <div className="flex-1 overflow-auto">
        <BlockNoteEditor
          initialContent={editorContent}
          onChange={setEditorContent}
        />
      </div>
    </div>
  );
}
