"use client";

import { useAtom, useAtomValue } from "jotai";
import { PanelRight } from "lucide-react";
import { usePathname } from "next/navigation";
import { currentThreadAtom } from "@/atoms/chat/current-thread.atom";
import { reportPanelAtom } from "@/atoms/chat/report-panel.atom";
import { documentsSidebarOpenAtom } from "@/atoms/documents/ui.atoms";
import { rightPanelCollapsedAtom } from "@/atoms/layout/right-panel.atom";
import { activeSearchSpaceIdAtom } from "@/atoms/search-spaces/search-space-query.atoms";
import { activeTabAtom } from "@/atoms/tabs/tabs.atom";
import { ChatHeader } from "@/components/new-chat/chat-header";
import { ChatShareButton } from "@/components/new-chat/chat-share-button";
import { Button } from "@/components/ui/button";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { useIsMobile } from "@/hooks/use-mobile";
import type { ChatVisibility, ThreadRecord } from "@/lib/chat/thread-persistence";

interface HeaderProps {
	mobileMenuTrigger?: React.ReactNode;
}

export function Header({ mobileMenuTrigger }: HeaderProps) {
	const pathname = usePathname();
	const searchSpaceId = useAtomValue(activeSearchSpaceIdAtom);
	const isMobile = useIsMobile();
	const activeTab = useAtomValue(activeTabAtom);

	const isChatPage = pathname?.includes("/new-chat") ?? false;
	const isDocumentTab = activeTab?.type === "document";

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

	const [collapsed, setCollapsed] = useAtom(rightPanelCollapsedAtom);
	const documentsOpen = useAtomValue(documentsSidebarOpenAtom);
	const reportState = useAtomValue(reportPanelAtom);
	const reportOpen = reportState.isOpen && !!reportState.reportId;
	const hasRightPanelContent = documentsOpen || reportOpen;
	const showExpandButton = !isMobile && collapsed && hasRightPanelContent;

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
			<div className="flex items-center gap-2">
				{hasThread && (
					<ChatShareButton thread={threadForButton} onVisibilityChange={handleVisibilityChange} />
				)}
				{showExpandButton && (
					<Tooltip>
						<TooltipTrigger asChild>
							<Button
								variant="ghost"
								size="icon"
								onClick={() => setCollapsed(false)}
								className="h-8 w-8 shrink-0"
							>
								<PanelRight className="h-4 w-4" />
								<span className="sr-only">Expand panel</span>
							</Button>
						</TooltipTrigger>
						<TooltipContent side="bottom">Expand panel</TooltipContent>
					</Tooltip>
				)}
			</div>
		</header>
	);
}
