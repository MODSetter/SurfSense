"use client";

import { Inbox, Megaphone, SquareLibrary } from "lucide-react";
import { useRouter } from "next/navigation";
import type { ReactNode } from "react";
import { Fragment, useCallback, useEffect, useMemo, useState } from "react";
import { useAnonymousMode } from "@/contexts/anonymous-mode";
import { useLoginGate } from "@/contexts/login-gate";
import { useIsMobile } from "@/hooks/use-mobile";
import { anonymousChatApiService } from "@/lib/apis/anonymous-chat-api.service";
import type { ChatItem, NavItem, PageUsage, SearchSpace } from "../types/layout.types";
import { LayoutShell } from "../ui/shell";

interface FreeLayoutDataProviderProps {
	children: ReactNode;
}

const GUEST_SPACE: SearchSpace = {
	id: 0,
	name: "SurfSense Free",
	description: "Free AI chat without login",
	isOwner: false,
	memberCount: 1,
};

export function FreeLayoutDataProvider({ children }: FreeLayoutDataProviderProps) {
	const router = useRouter();
	const { gate } = useLoginGate();
	const anonMode = useAnonymousMode();
	const isMobile = useIsMobile();
	const [quota, setQuota] = useState<{ used: number; limit: number } | null>(null);
	const [isDocsSidebarOpen, setIsDocsSidebarOpen] = useState(false);

	// Keep docs sidebar closed on mobile; auto-open only on desktop after hydration
	useEffect(() => {
		setIsDocsSidebarOpen(!isMobile);
	}, [isMobile]);

	useEffect(() => {
		anonymousChatApiService
			.getQuota()
			.then((q) => {
				setQuota({ used: q.used, limit: q.limit });
			})
			.catch(() => {});
	}, []);

	const resetChat = useCallback(() => {
		if (anonMode.isAnonymous) {
			anonMode.resetChat();
		}
	}, [anonMode]);

	const gatedAction = useCallback((feature: string) => () => gate(feature), [gate]);

	const navItems: NavItem[] = useMemo(
		() =>
			[
				{
					title: "Inbox",
					url: "#inbox",
					icon: Inbox,
					isActive: false,
				},
				isMobile
					? {
							title: "Documents",
							url: "#documents",
							icon: SquareLibrary,
							isActive: false,
						}
					: null,
				{
					title: "Announcements",
					url: "#announcements",
					icon: Megaphone,
					isActive: false,
				},
			].filter((item): item is NavItem => item !== null),
		[isMobile]
	);

	const pageUsage: PageUsage | undefined = quota
		? { pagesUsed: quota.used, pagesLimit: quota.limit }
		: undefined;

	const handleChatSelect = useCallback((_chat: ChatItem) => gate("view chat history"), [gate]);

	const handleNavItemClick = useCallback(
		(item: NavItem) => {
			if (item.title === "Inbox") gate("use the inbox");
			else if (item.title === "Documents") setIsDocsSidebarOpen((v) => !v);
			else if (item.title === "Announcements") gate("view announcements");
		},
		[gate]
	);

	const handleSearchSpaceSelect = useCallback(
		(_id: number) => gate("switch search spaces"),
		[gate]
	);

	return (
		<LayoutShell
			searchSpaces={[GUEST_SPACE]}
			activeSearchSpaceId={0}
			onSearchSpaceSelect={handleSearchSpaceSelect}
			onSearchSpaceSettings={gatedAction("search space settings")}
			onAddSearchSpace={gatedAction("create search spaces")}
			searchSpace={GUEST_SPACE}
			navItems={navItems}
			onNavItemClick={handleNavItemClick}
			chats={[]}
			sharedChats={[]}
			activeChatId={null}
			onNewChat={resetChat}
			onChatSelect={handleChatSelect}
			onChatRename={gatedAction("rename chats")}
			onChatDelete={gatedAction("delete chats")}
			onChatArchive={gatedAction("archive chats")}
			onViewAllSharedChats={gatedAction("view shared chats")}
			onViewAllPrivateChats={gatedAction("view chat history")}
			user={{
				email: "Guest",
				name: "Guest",
			}}
			onSettings={gatedAction("search space settings")}
			onManageMembers={gatedAction("team management")}
			onUserSettings={gatedAction("account settings")}
			onLogout={() => router.push("/register")}
			pageUsage={pageUsage}
			isChatPage
			isLoadingChats={false}
			documentsPanel={{
				open: isDocsSidebarOpen,
				onOpenChange: setIsDocsSidebarOpen,
			}}
		>
			<Fragment>{children}</Fragment>
		</LayoutShell>
	);
}
