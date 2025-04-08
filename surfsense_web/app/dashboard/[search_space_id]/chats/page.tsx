import { Suspense } from 'react';
import ChatsPageClient from './chats-client';

interface PageProps {
  params: {
    search_space_id: string;
  };
}

export default function ChatsPage({ params }: PageProps) {
  return (
    <Suspense fallback={<div className="flex items-center justify-center h-[60vh]">
      <div className="h-8 w-8 animate-spin rounded-full border-4 border-primary border-t-transparent"></div>
    </div>}>
      <ChatsPageClient searchSpaceId={params.search_space_id} />
    </Suspense>
  );
} 