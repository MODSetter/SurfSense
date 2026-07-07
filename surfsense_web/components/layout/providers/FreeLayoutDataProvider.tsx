"use client";

import { useRouter } from "next/navigation";
import type { ReactNode } from "react";
import { useCallback, useEffect, useState } from "react";
import { useAnonymousMode } from "@/contexts/anonymous-mode";
import { useLoginGate } from "@/contexts/login-gate";
import { useAnnouncements } from "@/hooks/use-announcements";
import { anonymousChatApiService } from "@/lib/apis/anonymous-chat-api.service";
import type { ChatItem, PageUsage, Workspace } from "../types/layout.types";
import { LayoutShell } from "../ui/shell";

interface FreeLayoutDataProviderProps {
	children: ReactNode;
}

const GUEST_SPACE: Workspace = {
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
	const { unreadCount: announcementUnreadCount } = useAnnouncements();
	const [quota, setQuota] = useState<{ used: number; limit: number } | null>(null);

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

	const pageUsage: PageUsage | undefined = quota
		? { pagesUsed: quota.used, pagesLimit: quota.limit }
		: undefined;

	const handleChatSelect = useCallback((_chat: ChatItem) => gate("view chat history"), [gate]);

	const handleAnnouncements = useCallback(() => gate("see what's new"), [gate]);

	const handleWorkspaceSelect = useCallback((_id: number) => gate("switch workspaces"), [gate]);

	return (
		<LayoutShell
			workspaces={[GUEST_SPACE]}
			activeWorkspaceId={0}
			onWorkspaceSelect={handleWorkspaceSelect}
			onWorkspaceSettings={gatedAction("workspace settings")}
			onAddWorkspace={gatedAction("create workspaces")}
			workspace={GUEST_SPACE}
			navItems={[]}
			chats={[]}
			activeChatId={null}
			onNewChat={resetChat}
			onChatSelect={handleChatSelect}
			onChatRename={gatedAction("rename chats")}
			onChatDelete={gatedAction("delete chats")}
			onChatArchive={gatedAction("archive chats")}
			onViewAllChats={gatedAction("view chat history")}
			user={{
				email: "Guest",
				name: "Guest",
			}}
			onSettings={gatedAction("workspace settings")}
			onManageMembers={gatedAction("team management")}
			onUserSettings={gatedAction("account settings")}
			onAnnouncements={handleAnnouncements}
			announcementUnreadCount={announcementUnreadCount}
			onLogout={() => router.push("/register")}
			pageUsage={pageUsage}
			isChatPage
			isLoadingChats={false}
		>
			{children}
		</LayoutShell>
	);
}
