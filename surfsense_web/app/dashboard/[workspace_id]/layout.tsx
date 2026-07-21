// Server component

import { cookies } from "next/headers";
import type React from "react";
import { DashboardClientLayout } from "./client-layout";

const PLAYGROUND_SIDEBAR_COLLAPSED_COOKIE = "surfsense_playground_sidebar_collapsed";

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

	return (
		<DashboardClientLayout
			workspaceId={workspace_id}
			initialPlaygroundSidebarCollapsed={initialPlaygroundSidebarCollapsed}
		>
			{children}
		</DashboardClientLayout>
	);
}
