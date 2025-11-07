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
			title: "Researcher",
			url: `/dashboard/${search_space_id}/researcher`,
			icon: "SquareTerminal",
			items: [],
		},
		{
			title: "Manage LLMs",
			url: `/dashboard/${search_space_id}/settings`,
			icon: "Settings2",
			items: [],
		},

		{
			title: "Sources",
			url: "#",
			icon: "Database",
			items: [
				{
					title: "Add Sources",
					url: `/dashboard/${search_space_id}/sources/add`,
				},
				{
					title: "Manage Documents",
					url: `/dashboard/${search_space_id}/documents`,
				},
				{
					title: "Manage Connectors",
					url: `/dashboard/${search_space_id}/connectors`,
				},
			],
		},
		{
			title: "Podcasts",
			url: `/dashboard/${search_space_id}/podcasts`,
			icon: "Podcast",
			items: [],
		},
		{
			title: "Logs",
			url: `/dashboard/${search_space_id}/logs`,
			icon: "FileText",
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
