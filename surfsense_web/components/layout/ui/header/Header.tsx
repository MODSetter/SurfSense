"use client";

import { useAtomValue } from "jotai";
import { usePathname } from "next/navigation";
import { currentThreadAtom } from "@/atoms/chat/current-thread.atom";
import { activeSearchSpaceIdAtom } from "@/atoms/search-spaces/search-space-query.atoms";
import { activeTabAtom } from "@/atoms/tabs/tabs.atom";
import { ActionLogButton } from "@/components/agent-action-log/action-log-button";
import { ChatShareButton } from "@/components/new-chat/chat-share-button";
import type { ThreadRecord } from "@/lib/chat/thread-persistence";

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
	const activeSearchSpaceId = searchSpaceId ? Number(searchSpaceId) : null;
	const canRenderShareButton =
		hasThread &&
		currentThreadState.id !== null &&
		currentThreadState.visibility !== null &&
		currentThreadState.searchSpaceId !== null &&
		activeSearchSpaceId !== null &&
		currentThreadState.searchSpaceId === activeSearchSpaceId;

	// Free chat pages have their own header with model selector; only render mobile trigger
	if (isFreePage) {
		if (!mobileMenuTrigger) return null;
		return (
			<header className="sticky top-0 z-10 flex h-14 shrink-0 items-center gap-2 bg-main-panel/95 backdrop-blur supports-backdrop-filter:bg-main-panel/60 px-4">
				{mobileMenuTrigger}
			</header>
		);
	}

	let threadForButton: ThreadRecord | null = null;
	if (
		canRenderShareButton &&
		currentThreadState.id !== null &&
		currentThreadState.visibility !== null &&
		currentThreadState.searchSpaceId !== null
	) {
		threadForButton = {
			id: currentThreadState.id,
			visibility: currentThreadState.visibility,
			created_by_id: null,
			search_space_id: currentThreadState.searchSpaceId,
			title: "",
			archived: false,
			created_at: "",
			updated_at: "",
		};
	}

	return (
		<header className="sticky top-0 z-10 flex h-14 shrink-0 items-center gap-2 bg-main-panel/95 backdrop-blur supports-backdrop-filter:bg-main-panel/60 px-4">
			{/* Left side - Mobile menu trigger */}
			<div className="flex flex-1 items-center gap-2 min-w-0">{mobileMenuTrigger}</div>

			{/* Right side - Actions */}
			<div className="ml-auto flex items-center gap-2">
				{hasThread && <ActionLogButton threadId={currentThreadState.id} />}
				{threadForButton && <ChatShareButton thread={threadForButton} />}
			</div>
		</header>
	);
}
