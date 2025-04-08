"use client";
import React, { useEffect } from 'react';
import { useParams, useRouter } from 'next/navigation';
import { Loader2 } from 'lucide-react';

const ResearcherPage = () => {
  const router = useRouter();
  const { search_space_id } = useParams();
  const [isCreating, setIsCreating] = React.useState(true);
  const [error, setError] = React.useState<string | null>(null);

  useEffect(() => {
    const createChat = async () => {
      try {
        // Get token from localStorage
        const token = localStorage.getItem('surfsense_bearer_token');
        
        if (!token) {
          setError('Authentication token not found');
          setIsCreating(false);
          return;
        }

        // Create a new chat
        const response = await fetch(`${process.env.NEXT_PUBLIC_FASTAPI_BACKEND_URL}/api/v1/chats/`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'Authorization': `Bearer ${token}`
          },
          body: JSON.stringify({
            type: "GENERAL",
            title: "Untitled Chat", // Empty title initially
            initial_connectors: ["CRAWLED_URL"], // Default connector
            messages: [],
            search_space_id: Number(search_space_id)
          })
        });

        if (!response.ok) {
          throw new Error(`Failed to create chat: ${response.statusText}`);
        }

        const data = await response.json();
        
        // Redirect to the new chat page
        router.push(`/dashboard/${search_space_id}/researcher/${data.id}`);
      } catch (err) {
        console.error('Error creating chat:', err);
        setError(err instanceof Error ? err.message : 'Failed to create chat');
        setIsCreating(false);
      }
    };

    createChat();
  }, [search_space_id, router]);

  if (error) {
    return (
      <div className="flex flex-col items-center justify-center min-h-[calc(100vh-4rem)]">
        <div className="text-red-500 mb-4">Error: {error}</div>
        <button 
          onClick={() => location.reload()}
          className="px-4 py-2 bg-primary text-white rounded-md"
        >
          Try Again
        </button>
      </div>
    );
  }

  return (
    <div className="flex flex-col items-center justify-center min-h-[calc(100vh-4rem)]">
      <Loader2 className="h-8 w-8 animate-spin text-primary mb-4" />
      <p className="text-muted-foreground">Creating new research chat...</p>
    </div>
  );
};

export default ResearcherPage;