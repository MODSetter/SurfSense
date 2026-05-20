"use client";

import { useAtomValue } from "jotai";
import { usePathname } from "next/navigation";
import { currentThreadAtom } from "@/atoms/chat/current-thread.atom";
import { activeSearchSpaceIdAtom } from "@/atoms/search-spaces/search-space-query.atoms";
import { activeTabAtom } from "@/atoms/tabs/tabs.atom";
import { ActionLogButton } from "@/components/agent-action-log/action-log-button";
import { ChatHeader } from "@/components/new-chat/chat-header";
import { ChatShareButton } from "@/components/new-chat/chat-share-button";
import type { ChatVisibility, ThreadRecord } from "@/lib/chat/thread-persistence";

interface HeaderProps {
	mobileMenuTrigger?: React.ReactNode;
}

export function Header({ mobileMenuTrigger }: HeaderProps) {
	const pathname = usePathname();
	const searchSpaceId = useAtomValue(activeSearchSpaceIdAtom);
	const activeTab = useAtomValue(activeTabAtom);

	const isFreePage = pathname?.startsWith("/free") ?? false;
	const isChatPage = pathname?.includes("/new-chat") ?? false;
	const isDocumentTab = activeTab?.type === "document";

	const currentThreadState = useAtomValue(currentThreadAtom);

	const hasThread = isChatPage && !isDocumentTab && currentThreadState.id !== null;

	// Free chat pages have their own header with model selector; only render mobile trigger
	if (isFreePage) {
		if (!mobileMenuTrigger) return null;
		return (
			<header className="sticky top-0 z-10 flex h-14 shrink-0 items-center gap-2 bg-main-panel/95 backdrop-blur supports-backdrop-filter:bg-main-panel/60 px-4">
				{mobileMenuTrigger}
			</header>
		);
	}

	const threadForButton: ThreadRecord | null =
		hasThread && currentThreadState.id !== null
			? {
					id: currentThreadState.id,
					visibility: currentThreadState.visibility ?? "PRIVATE",
					created_by_id: null,
					search_space_id: 0,
					title: "",
					archived: false,
					created_at: "",
					updated_at: "",
				}
			: null;

	const handleVisibilityChange = (_visibility: ChatVisibility) => {};

	return (
		<header className="sticky top-0 z-10 flex h-14 shrink-0 items-center gap-2 bg-main-panel/95 backdrop-blur supports-backdrop-filter:bg-main-panel/60 px-4">
			{/* Left side - Mobile menu trigger + Model selector */}
			<div className="flex flex-1 items-center gap-2 min-w-0">
				{mobileMenuTrigger}
				{isChatPage && !isDocumentTab && searchSpaceId && (
					<ChatHeader searchSpaceId={Number(searchSpaceId)} className="md:h-9 md:px-4 md:text-sm" />
				)}
			</div>

			{/* Right side - Actions */}
			<div className="ml-auto flex items-center gap-2">
				{hasThread && <ActionLogButton threadId={currentThreadState.id} />}
				{hasThread && (
					<ChatShareButton thread={threadForButton} onVisibilityChange={handleVisibilityChange} />
				)}
			</div>
		</header>
	);
}
