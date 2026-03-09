// Server component
import type React from "react";
import { use } from "react";
import { DashboardClientLayout } from "./client-layout";

export default function DashboardLayout({
	params,
	children,
}: {
	params: Promise<{ search_space_id: string }>;
	children: React.ReactNode;
}) {
	const { search_space_id } = use(params);

	return <DashboardClientLayout searchSpaceId={search_space_id}>{children}</DashboardClientLayout>;
}
