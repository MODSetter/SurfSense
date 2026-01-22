"use client";

import { useAtomValue } from "jotai";
import { usePathname } from "next/navigation";
import { currentThreadAtom } from "@/atoms/chat/current-thread.atom";
import { ChatShareButton } from "@/components/new-chat/chat-share-button";
import type { ChatVisibility, ThreadRecord } from "@/lib/chat/thread-persistence";

interface HeaderProps {
	breadcrumb?: React.ReactNode;
	mobileMenuTrigger?: React.ReactNode;
}

export function Header({ breadcrumb, mobileMenuTrigger }: HeaderProps) {
	const pathname = usePathname();

	// Check if we're on a chat page
	const isChatPage = pathname?.includes("/new-chat") ?? false;

	// Use Jotai atom for thread state (synced from chat page)
	const currentThreadState = useAtomValue(currentThreadAtom);

	// Show button only when we have a thread id (thread exists and is synced to Jotai)
	const hasThread = isChatPage && currentThreadState.id !== null;

	// Create minimal thread object for ChatShareButton (used for API calls)
	const threadForButton: ThreadRecord | null =
		hasThread && currentThreadState.id !== null
			? {
					id: currentThreadState.id,
					visibility: currentThreadState.visibility ?? "PRIVATE",
					// These fields are not used by ChatShareButton for display, only for checks
					created_by_id: null,
					search_space_id: 0,
					title: "",
					archived: false,
					created_at: "",
					updated_at: "",
				}
			: null;

	const handleVisibilityChange = (_visibility: ChatVisibility) => {
		// Visibility change is handled by ChatShareButton internally via Jotai
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
			<div className="flex items-center gap-4">
				{/* Share button - only show on chat pages when thread exists */}
				{hasThread && (
					<ChatShareButton thread={threadForButton} onVisibilityChange={handleVisibilityChange} />
				)}
			</div>
		</header>
	);
}
