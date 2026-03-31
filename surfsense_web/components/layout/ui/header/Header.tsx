"use client";

import { useAtomValue } from "jotai";
import { usePathname } from "next/navigation";
import { currentThreadAtom } from "@/atoms/chat/current-thread.atom";
import { hitlEditPanelAtom } from "@/atoms/chat/hitl-edit-panel.atom";
import { reportPanelAtom } from "@/atoms/chat/report-panel.atom";
import { documentsSidebarOpenAtom } from "@/atoms/documents/ui.atoms";
import { editorPanelAtom } from "@/atoms/editor/editor-panel.atom";
import { rightPanelCollapsedAtom } from "@/atoms/layout/right-panel.atom";
import { activeSearchSpaceIdAtom } from "@/atoms/search-spaces/search-space-query.atoms";
import { activeTabAtom, tabsAtom } from "@/atoms/tabs/tabs.atom";
import { ChatHeader } from "@/components/new-chat/chat-header";
import { ChatShareButton } from "@/components/new-chat/chat-share-button";
import { useIsMobile } from "@/hooks/use-mobile";
import type { ChatVisibility, ThreadRecord } from "@/lib/chat/thread-persistence";
import { cn } from "@/lib/utils";

interface HeaderProps {
	mobileMenuTrigger?: React.ReactNode;
}

export function Header({ mobileMenuTrigger }: HeaderProps) {
	const pathname = usePathname();
	const searchSpaceId = useAtomValue(activeSearchSpaceIdAtom);
	const isMobile = useIsMobile();
	const activeTab = useAtomValue(activeTabAtom);
	const tabs = useAtomValue(tabsAtom);
	const collapsed = useAtomValue(rightPanelCollapsedAtom);
	const documentsOpen = useAtomValue(documentsSidebarOpenAtom);
	const reportState = useAtomValue(reportPanelAtom);
	const editorState = useAtomValue(editorPanelAtom);
	const hitlEditState = useAtomValue(hitlEditPanelAtom);

	const isChatPage = pathname?.includes("/new-chat") ?? false;
	const isDocumentTab = activeTab?.type === "document";
	const reportOpen = reportState.isOpen && !!reportState.reportId;
	const editorOpen = editorState.isOpen && !!editorState.documentId;
	const hitlEditOpen = hitlEditState.isOpen && !!hitlEditState.onSave;
	const showExpandButton =
		!isMobile && collapsed && (documentsOpen || reportOpen || editorOpen || hitlEditOpen);
	const hasTabBar = tabs.length > 1;

	const currentThreadState = useAtomValue(currentThreadAtom);

	const hasThread = isChatPage && !isDocumentTab && currentThreadState.id !== null;

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
			<div
				className={cn("ml-auto flex items-center gap-2", showExpandButton && !hasTabBar && "mr-10")}
			>
				{hasThread && (
					<ChatShareButton thread={threadForButton} onVisibilityChange={handleVisibilityChange} />
				)}
			</div>
		</header>
	);
}
