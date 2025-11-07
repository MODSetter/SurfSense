"use client";

import {
	AlertCircle,
	BookOpen,
	Cable,
	Database,
	ExternalLink,
	FileStack,
	FileText,
	Info,
	type LucideIcon,
	MessageCircleMore,
	Podcast,
	Settings2,
	SquareLibrary,
	SquareTerminal,
	Trash2,
	Undo2,
} from "lucide-react";
import Image from "next/image";
import Link from "next/link";
import { memo, useMemo } from "react";

import { Logo } from "@/components/Logo";
import { NavMain } from "@/components/sidebar/nav-main";
import { NavProjects } from "@/components/sidebar/nav-projects";
import { NavSecondary } from "@/components/sidebar/nav-secondary";
import { PageUsageDisplay } from "@/components/sidebar/page-usage-display";
import {
	Sidebar,
	SidebarContent,
	SidebarFooter,
	SidebarHeader,
	SidebarMenu,
	SidebarMenuButton,
	SidebarMenuItem,
} from "@/components/ui/sidebar";

// Map of icon names to their components
export const iconMap: Record<string, LucideIcon> = {
	BookOpen,
	Cable,
	Database,
	FileStack,
	Undo2,
	MessageCircleMore,
	Settings2,
	SquareLibrary,
	SquareTerminal,
	AlertCircle,
	Info,
	ExternalLink,
	Trash2,
	Podcast,
	FileText,
};

const defaultData = {
	user: {
		name: "Surf",
		email: "m@example.com",
		avatar: "/icon-128.png",
	},
	navMain: [
		{
			title: "Researcher",
			url: "#",
			icon: "SquareTerminal",
			isActive: true,
			items: [],
		},
		{
			title: "Sources",
			url: "#",
			icon: "Database",
			items: [
				{
					title: "Add Sources",
					url: "#",
				},
				{
					title: "Manage Documents",
					url: "#",
				},
				{
					title: "Manage Connectors",
					url: "#",
				},
			],
		},
	],
	navSecondary: [
		{
			title: "SEARCH SPACE",
			url: "#",
			icon: "LifeBuoy",
		},
	],
	RecentChats: [
		{
			name: "Design Engineering",
			url: "#",
			icon: "MessageCircleMore",
			id: 1001,
		},
		{
			name: "Sales & Marketing",
			url: "#",
			icon: "MessageCircleMore",
			id: 1002,
		},
		{
			name: "Travel",
			url: "#",
			icon: "MessageCircleMore",
			id: 1003,
		},
	],
};

interface AppSidebarProps extends React.ComponentProps<typeof Sidebar> {
	navMain?: {
		title: string;
		url: string;
		icon: string;
		isActive?: boolean;
		items?: {
			title: string;
			url: string;
		}[];
	}[];
	navSecondary?: {
		title: string;
		url: string;
		icon: string;
	}[];
	RecentChats?: {
		name: string;
		url: string;
		icon: string;
		id?: number;
		search_space_id?: number;
		actions?: {
			name: string;
			icon: string;
			onClick: () => void;
		}[];
	}[];
	user?: {
		name: string;
		email: string;
		avatar: string;
	};
	pageUsage?: {
		pagesUsed: number;
		pagesLimit: number;
	};
}

// Memoized AppSidebar component for better performance
export const AppSidebar = memo(function AppSidebar({
	navMain = defaultData.navMain,
	navSecondary = defaultData.navSecondary,
	RecentChats = defaultData.RecentChats,
	pageUsage,
	...props
}: AppSidebarProps) {
	// Process navMain to resolve icon names to components
	const processedNavMain = useMemo(() => {
		return navMain.map((item) => ({
			...item,
			icon: iconMap[item.icon] || SquareTerminal,
		}));
	}, [navMain]);

	// Process navSecondary to resolve icon names to components
	const processedNavSecondary = useMemo(() => {
		return navSecondary.map((item) => ({
			...item,
			icon: iconMap[item.icon] || Undo2,
		}));
	}, [navSecondary]);

	// Process RecentChats to resolve icon names to components
	const processedRecentChats = useMemo(() => {
		return (
			RecentChats?.map((item) => ({
				...item,
				icon: iconMap[item.icon] || MessageCircleMore,
			})) || []
		);
	}, [RecentChats]);

	return (
		<Sidebar variant="inset" collapsible="icon" aria-label="Main navigation" {...props}>
			<SidebarHeader>
				<SidebarMenu>
					<SidebarMenuItem>
						<SidebarMenuButton asChild size="lg">
							<Link href="/" className="flex items-center gap-2 w-full">
								<div className="bg-sidebar-primary text-sidebar-primary-foreground flex aspect-square size-8 items-center justify-center rounded-lg">
									<Image
										src="/icon-128.png"
										alt="SurfSense logo"
										width={32}
										height={32}
										className="rounded-lg"
									/>
								</div>
								<div className="grid flex-1 text-left text-sm leading-tight">
									<span className="truncate font-medium">SurfSense</span>
									<span className="truncate text-xs">beta v0.0.8</span>
								</div>
							</Link>
						</SidebarMenuButton>
					</SidebarMenuItem>
				</SidebarMenu>
			</SidebarHeader>

			<SidebarContent className="space-y-6">
				<NavMain items={processedNavMain} />

				{processedRecentChats.length > 0 && (
					<div className="space-y-2">
						<NavProjects chats={processedRecentChats} />
					</div>
				)}
			</SidebarContent>
			<SidebarFooter>
				{pageUsage && (
					<PageUsageDisplay pagesUsed={pageUsage.pagesUsed} pagesLimit={pageUsage.pagesLimit} />
				)}
				<NavSecondary items={processedNavSecondary} className="mt-auto" />
			</SidebarFooter>
		</Sidebar>
	);
});
