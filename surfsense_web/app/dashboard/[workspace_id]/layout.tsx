// Server component

import { cookies } from "next/headers";
import type React from "react";
import {
	parseSidebarPreferences,
	SIDEBAR_COLLAPSED_COOKIE,
	SIDEBAR_WIDTH_COOKIE,
} from "@/components/layout/sidebar-preferences";
import {
	parseRetrievalScopeCookie,
	RETRIEVAL_SCOPE_COOKIE,
} from "@/lib/chat/retrieval-scope-preferences";
import { DashboardClientLayout } from "./client-layout";

const PLAYGROUND_SIDEBAR_COLLAPSED_COOKIE = "surfsense_playground_sidebar_collapsed";
const RIGHT_PANEL_COLLAPSED_COOKIE = "surfsense_right_panel_collapsed";

function sessionUserId(token: string | undefined): string | undefined {
	if (!token) return undefined;
	try {
		const encodedPayload = decodeURIComponent(token).split(".")[1];
		if (!encodedPayload) return undefined;
		const payload = JSON.parse(Buffer.from(encodedPayload, "base64url").toString("utf8")) as {
			sub?: unknown;
		};
		return typeof payload.sub === "string" ? payload.sub : undefined;
	} catch {
		return undefined;
	}
}

export default async function DashboardLayout({
	params,
	children,
}: {
	params: Promise<{ workspace_id: string }>;
	children: React.ReactNode;
}) {
	const [{ workspace_id }, cookieStore] = await Promise.all([params, cookies()]);
	const initialPlaygroundSidebarCollapsed =
		cookieStore.get(PLAYGROUND_SIDEBAR_COLLAPSED_COOKIE)?.value === "true";
	const initialRightPanelCollapsed =
		cookieStore.get(RIGHT_PANEL_COLLAPSED_COOKIE)?.value === "true";
	const initialSidebarPreferences = parseSidebarPreferences(
		cookieStore.get(SIDEBAR_COLLAPSED_COOKIE)?.value,
		cookieStore.get(SIDEBAR_WIDTH_COOKIE)?.value
	);
	const currentUserId = sessionUserId(
		cookieStore.get(process.env.SESSION_COOKIE_NAME ?? "surfsense_session")?.value
	);
	const initialRetrievalScope = parseRetrievalScopeCookie(
		cookieStore.get(RETRIEVAL_SCOPE_COOKIE)?.value,
		currentUserId
	);

	return (
		<DashboardClientLayout
			workspaceId={workspace_id}
			initialRetrievalScope={initialRetrievalScope}
			initialSidebarCollapsed={initialSidebarPreferences.collapsed}
			initialSidebarWidth={initialSidebarPreferences.width}
			initialPlaygroundSidebarCollapsed={initialPlaygroundSidebarCollapsed}
			initialRightPanelCollapsed={initialRightPanelCollapsed}
		>
			{children}
		</DashboardClientLayout>
	);
}
