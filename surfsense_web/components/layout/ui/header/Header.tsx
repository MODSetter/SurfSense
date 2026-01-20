"use client";

import { useQuery } from "@tanstack/react-query";
import { useParams, usePathname } from "next/navigation";
import { NotificationButton } from "@/components/notifications/NotificationButton";
import { ChatShareButton } from "@/components/new-chat/chat-share-button";
import { getThreadFull } from "@/lib/chat/thread-persistence";
import type { ChatVisibility } from "@/lib/chat/thread-persistence";

interface HeaderProps {
	breadcrumb?: React.ReactNode;
	mobileMenuTrigger?: React.ReactNode;
}

export function Header({
	breadcrumb,
	mobileMenuTrigger,
}: HeaderProps) {
	const params = useParams();
	const pathname = usePathname();
	
	// Check if we're on a chat page
	const isChatPage = pathname?.includes("/new-chat") ?? false;
	
	// Get chat_id from URL params
	const chatId = params?.chat_id
		? Number(Array.isArray(params.chat_id) ? params.chat_id[0] : params.chat_id)
		: null;

	// Fetch current thread if on chat page and chat_id exists
	const { data: currentThread } = useQuery({
		queryKey: ["thread", chatId],
		queryFn: () => getThreadFull(chatId!),
		enabled: isChatPage && chatId !== null && chatId > 0,
	});

	const handleVisibilityChange = (visibility: ChatVisibility) => {
		// Visibility change is handled by ChatShareButton internally
		// This callback can be used for additional side effects if needed
	};

	return (
		<header className="sticky top-0 z-10 flex h-14 shrink-0 items-center gap-2 border-b bg-background/95 backdrop-blur supports-backdrop-filter:bg-background/60 px-4">
			{/* Left side - Mobile menu trigger + Breadcrumb */}
			<div className="flex flex-1 items-center gap-2 min-w-0">
				{mobileMenuTrigger}
				<div className="hidden md:block">{breadcrumb}</div>
			</div>

			{/* Right side - Actions */}
			<div className="flex items-center gap-2">
				{/* Notifications */}
				<NotificationButton />
				{/* Share button - only show on chat pages when thread exists */}
				{isChatPage && currentThread && (
					<ChatShareButton
						thread={currentThread}
						onVisibilityChange={handleVisibilityChange}
					/>
				)}
			</div>
		</header>
	);
}
