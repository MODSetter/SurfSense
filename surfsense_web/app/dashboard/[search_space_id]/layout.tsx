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
	// Use React.use to unwrap the params Promise
	const { search_space_id } = use(params);

	const customNavSecondary = [
		{
			title: `All Search Spaces`,
			url: `#`,
			icon: "Info",
		},
		{
			title: `All Search Spaces`,
			url: "/dashboard",
			icon: "Undo2",
		},
	];

	const customNavMain = [
		{
			title: "Chat",
			url: `/dashboard/${search_space_id}/new-chat`,
			icon: "MessageCircle",
			items: [],
		},
		{
			title: "Documents",
			url: `/dashboard/${search_space_id}/documents`,
			icon: "SquareLibrary",
			items: [],
		},
	];

	return (
		<DashboardClientLayout
			searchSpaceId={search_space_id}
			navSecondary={customNavSecondary}
			navMain={customNavMain}
		>
			{children}
		</DashboardClientLayout>
	);
}
