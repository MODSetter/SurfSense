// Server component

import { cookies } from "next/headers";
import type React from "react";
import {
	parseSidebarPreferences,
	SIDEBAR_COLLAPSED_COOKIE,
	SIDEBAR_WIDTH_COOKIE,
} from "@/components/layout/sidebar-preferences";
import { DashboardClientLayout } from "./client-layout";

const PLAYGROUND_SIDEBAR_COLLAPSED_COOKIE = "surfsense_playground_sidebar_collapsed";
const RIGHT_PANEL_COLLAPSED_COOKIE = "surfsense_right_panel_collapsed";

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

	return (
		<DashboardClientLayout
			workspaceId={workspace_id}
			initialSidebarCollapsed={initialSidebarPreferences.collapsed}
			initialSidebarWidth={initialSidebarPreferences.width}
			initialPlaygroundSidebarCollapsed={initialPlaygroundSidebarCollapsed}
			initialRightPanelCollapsed={initialRightPanelCollapsed}
		>
			{children}
		</DashboardClientLayout>
	);
}
