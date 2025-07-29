"use client";

import {
	AlertCircle,
	BookOpen,
	Cable,
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
import { useMemo } from "react";

import { Logo } from "@/components/Logo";
import { NavMain } from "@/components/sidebar/nav-main";
import { NavProjects } from "@/components/sidebar/nav-projects";
import { NavSecondary } from "@/components/sidebar/nav-secondary";
import {
	Sidebar,
	SidebarContent,
	SidebarHeader,
	SidebarMenu,
	SidebarMenuButton,
	SidebarMenuItem,
} from "@/components/ui/sidebar";

// Map of icon names to their components
export const iconMap: Record<string, LucideIcon> = {
	BookOpen,
	Cable,
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
			title: "Documents",
			url: "#",
			icon: "FileStack",
			items: [
				{
					title: "Upload Documents",
					url: "#",
				},
				{
					title: "Manage Documents",
					url: "#",
				},
			],
		},
		{
			title: "Connectors",
			url: "#",
			icon: "Cable",
			items: [
				{
					title: "Add Connector",
					url: "#",
				},
				{
					title: "Manage Connectors",
					url: "#",
				},
			],
		},
		{
			title: "Research Synthesizer's",
			url: "#",
			icon: "SquareLibrary",
			items: [
				{
					title: "Podcast Creator",
					url: "#",
				},
				{
					title: "Presentation Creator",
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
		icon: string; // Changed to string (icon name)
	}[];
	RecentChats?: {
		name: string;
		url: string;
		icon: string; // Changed to string (icon name)
		id?: number;
		search_space_id?: number;
		actions?: {
			name: string;
			icon: string;
			onClick: () => void;
		}[];
	}[];
}

export function AppSidebar({
	navMain = defaultData.navMain,
	navSecondary = defaultData.navSecondary,
	RecentChats = defaultData.RecentChats,
	...props
}: AppSidebarProps) {
	// Process navMain to resolve icon names to components
	const processedNavMain = useMemo(() => {
		return navMain.map((item) => ({
			...item,
			icon: iconMap[item.icon] || SquareTerminal, // Fallback to SquareTerminal if icon not found
		}));
	}, [navMain]);

	// Process navSecondary to resolve icon names to components
	const processedNavSecondary = useMemo(() => {
		return navSecondary.map((item) => ({
			...item,
			icon: iconMap[item.icon] || Undo2, // Fallback to Undo2 if icon not found
		}));
	}, [navSecondary]);

	// Process RecentChats to resolve icon names to components
	const processedRecentChats = useMemo(() => {
		return (
			RecentChats?.map((item) => ({
				...item,
				icon: iconMap[item.icon] || MessageCircleMore, // Fallback to MessageCircleMore if icon not found
			})) || []
		);
	}, [RecentChats]);

	return (
		<Sidebar variant="inset" {...props}>
			<SidebarHeader>
				<SidebarMenu>
					<SidebarMenuItem>
						<SidebarMenuButton size="lg" asChild>
							<div>
								<div className="bg-sidebar-primary text-sidebar-primary-foreground flex aspect-square size-8 items-center justify-center rounded-lg">
									<Logo className="rounded-lg" />
								</div>
								<div className="grid flex-1 text-left text-sm leading-tight">
									<span className="truncate font-medium">SurfSense</span>
									<span className="truncate text-xs">beta v0.0.7</span>
								</div>
							</div>
						</SidebarMenuButton>
					</SidebarMenuItem>
				</SidebarMenu>
			</SidebarHeader>
			<SidebarContent>
				<NavMain items={processedNavMain} />
				{processedRecentChats.length > 0 && <NavProjects chats={processedRecentChats} />}
				<NavSecondary items={processedNavSecondary} className="mt-auto" />
			</SidebarContent>
		</Sidebar>
	);
}
