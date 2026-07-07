// Server component
import type React from "react";
import { use } from "react";
import { DashboardClientLayout } from "./client-layout";

export default function DashboardLayout({
	params,
	children,
}: {
	params: Promise<{ workspace_id: string }>;
	children: React.ReactNode;
}) {
	const { workspace_id } = use(params);

	return <DashboardClientLayout workspaceId={workspace_id}>{children}</DashboardClientLayout>;
}
