"use client";

import { useAtomValue } from "jotai";
import {
	AlertCircle,
	BookOpen,
	Cable,
	ChevronsUpDown,
	Database,
	ExternalLink,
	FileStack,
	FileText,
	Info,
	LogOut,
	type LucideIcon,
	MessageCircleMore,
	MoonIcon,
	Podcast,
	RefreshCw,
	Settings2,
	SquareLibrary,
	SquareTerminal,
	SunIcon,
	Trash2,
	Undo2,
	UserPlus,
	Users,
} from "lucide-react";
import { useRouter } from "next/navigation";
import { useTheme } from "next-themes";
import { memo, useEffect, useMemo, useState } from "react";
import { currentUserAtom } from "@/atoms/user/user-query.atoms";
import {
	DropdownMenu,
	DropdownMenuContent,
	DropdownMenuGroup,
	DropdownMenuItem,
	DropdownMenuLabel,
	DropdownMenuSeparator,
	DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";

/**
 * Generates a consistent color based on a string (email)
 */
function stringToColor(str: string): string {
	let hash = 0;
	for (let i = 0; i < str.length; i++) {
		hash = str.charCodeAt(i) + ((hash << 5) - hash);
	}
	const colors = [
		"#6366f1", // indigo
		"#8b5cf6", // violet
		"#a855f7", // purple
		"#d946ef", // fuchsia
		"#ec4899", // pink
		"#f43f5e", // rose
		"#ef4444", // red
		"#f97316", // orange
		"#eab308", // yellow
		"#84cc16", // lime
		"#22c55e", // green
		"#14b8a6", // teal
		"#06b6d4", // cyan
		"#0ea5e9", // sky
		"#3b82f6", // blue
	];
	return colors[Math.abs(hash) % colors.length];
}

/**
 * Gets initials from an email address
 */
function getInitials(email: string): string {
	const name = email.split("@")[0];
	const parts = name.split(/[._-]/);
	if (parts.length >= 2) {
		return (parts[0][0] + parts[1][0]).toUpperCase();
	}
	return name.slice(0, 2).toUpperCase();
}

/**
 * Dynamic avatar component that generates an SVG based on email
 */
function UserAvatar({ email, size = 32 }: { email: string; size?: number }) {
	const bgColor = stringToColor(email);
	const initials = getInitials(email);

	return (
		<svg
			width={size}
			height={size}
			viewBox="0 0 32 32"
			className="rounded-lg"
			role="img"
			aria-labelledby="sidebar-avatar-title"
		>
			<title id="sidebar-avatar-title">Avatar for {email}</title>
			<rect width="32" height="32" rx="6" fill={bgColor} />
			<text
				x="50%"
				y="50%"
				dominantBaseline="central"
				textAnchor="middle"
				fill="white"
				fontSize="12"
				fontWeight="600"
				fontFamily="system-ui, sans-serif"
			>
				{initials}
			</text>
		</svg>
	);
}

import { NavChats } from "@/components/sidebar/nav-chats";
import { NavMain } from "@/components/sidebar/nav-main";
import { NavNotes } from "@/components/sidebar/nav-notes";
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
	FileText,
	SquareTerminal,
	AlertCircle,
	Info,
	ExternalLink,
	Trash2,
	Podcast,
	Users,
	RefreshCw,
};

const defaultData = {
	user: {
		name: "Surf",
		email: "m@example.com",
		avatar: "/icon-128.png",
	},
	navMain: [
		{
			title: "Chat",
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
	RecentNotes: [
		{
			name: "Meeting Notes",
			url: "#",
			icon: "FileText",
			id: 2001,
		},
		{
			name: "Project Ideas",
			url: "#",
			icon: "FileText",
			id: 2002,
		},
	],
};

interface AppSidebarProps extends React.ComponentProps<typeof Sidebar> {
	searchSpaceId?: string;
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
	RecentNotes?: {
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
	onAddNote?: () => void;
}

// Memoized AppSidebar component for better performance
export const AppSidebar = memo(function AppSidebar({
	searchSpaceId,
	navMain = defaultData.navMain,
	navSecondary = defaultData.navSecondary,
	RecentChats = defaultData.RecentChats,
	RecentNotes = defaultData.RecentNotes,
	pageUsage,
	onAddNote,
	...props
}: AppSidebarProps) {
	const router = useRouter();
	const { theme, setTheme } = useTheme();
	const { data: user, isPending: isLoadingUser } = useAtomValue(currentUserAtom);
	const [isClient, setIsClient] = useState(false);
	const [isSourcesExpanded, setIsSourcesExpanded] = useState(false);

	useEffect(() => {
		setIsClient(true);
	}, []);

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

	// Process RecentNotes to resolve icon names to components
	const processedRecentNotes = useMemo(() => {
		return (
			RecentNotes?.map((item) => ({
				...item,
				icon: iconMap[item.icon] || FileText,
			})) || []
		);
	}, [RecentNotes]);

	// Get user display name from email
	const userDisplayName = user?.email ? user.email.split("@")[0] : "User";
	const userEmail = user?.email || (isLoadingUser ? "Loading..." : "Unknown");

	const handleLogout = () => {
		try {
			if (typeof window !== "undefined") {
				localStorage.removeItem("surfsense_bearer_token");
				router.push("/");
			}
		} catch (error) {
			console.error("Error during logout:", error);
			router.push("/");
		}
	};

	return (
		<Sidebar variant="inset" collapsible="icon" aria-label="Main navigation" {...props}>
			<SidebarHeader>
				<SidebarMenu>
					<SidebarMenuItem>
						<DropdownMenu>
							<DropdownMenuTrigger asChild>
								<SidebarMenuButton
									size="lg"
									className="data-[state=open]:bg-sidebar-accent data-[state=open]:text-sidebar-accent-foreground"
								>
									<div className="flex aspect-square size-8 items-center justify-center">
										{user?.email ? (
											<UserAvatar email={user.email} size={32} />
										) : (
											<div className="size-8 rounded-lg bg-sidebar-primary animate-pulse" />
										)}
									</div>
									<div className="grid flex-1 text-left text-sm leading-tight">
										<span className="truncate font-medium">{userDisplayName}</span>
										<span className="truncate text-xs text-muted-foreground">{userEmail}</span>
									</div>
									<ChevronsUpDown className="ml-auto size-4" />
								</SidebarMenuButton>
							</DropdownMenuTrigger>
							<DropdownMenuContent
								className="w-[--radix-dropdown-menu-trigger-width] min-w-56 rounded-lg"
								side="bottom"
								align="start"
								sideOffset={4}
							>
								<DropdownMenuLabel className="p-0 font-normal">
									<div className="flex items-center gap-2 px-1 py-1.5 text-left text-sm">
										<div className="flex aspect-square size-8 items-center justify-center">
											{user?.email ? (
												<UserAvatar email={user.email} size={32} />
											) : (
												<div className="size-8 rounded-lg bg-sidebar-primary animate-pulse" />
											)}
										</div>
										<div className="grid flex-1 text-left text-sm leading-tight">
											<span className="truncate font-medium">{userDisplayName}</span>
											<span className="truncate text-xs text-muted-foreground">{userEmail}</span>
										</div>
									</div>
								</DropdownMenuLabel>
								<DropdownMenuSeparator />
								<DropdownMenuGroup>
									{searchSpaceId && (
										<>
											<DropdownMenuItem
												onClick={() => router.push(`/dashboard/${searchSpaceId}/settings`)}
											>
												<Settings2 className="mr-2 h-4 w-4" />
												Settings
											</DropdownMenuItem>
											<DropdownMenuItem
												onClick={() => router.push(`/dashboard/${searchSpaceId}/team`)}
											>
												<UserPlus className="mr-2 h-4 w-4" />
												Invite members
											</DropdownMenuItem>
										</>
									)}
									<DropdownMenuItem onClick={() => router.push("/dashboard")}>
										<SquareLibrary className="mr-2 h-4 w-4" />
										Switch workspace
									</DropdownMenuItem>
								</DropdownMenuGroup>
								<DropdownMenuSeparator />
								<DropdownMenuGroup>
									{isClient && (
										<DropdownMenuItem onClick={() => setTheme(theme === "dark" ? "light" : "dark")}>
											{theme === "dark" ? (
												<SunIcon className="mr-2 h-4 w-4" />
											) : (
												<MoonIcon className="mr-2 h-4 w-4" />
											)}
											{theme === "dark" ? "Light mode" : "Dark mode"}
										</DropdownMenuItem>
									)}
								</DropdownMenuGroup>
								<DropdownMenuSeparator />
								<DropdownMenuItem onClick={handleLogout}>
									<LogOut className="mr-2 h-4 w-4" />
									Logout
								</DropdownMenuItem>
							</DropdownMenuContent>
						</DropdownMenu>
					</SidebarMenuItem>
				</SidebarMenu>
			</SidebarHeader>

			<SidebarContent className="gap-1">
				<NavMain items={processedNavMain} onSourcesExpandedChange={setIsSourcesExpanded} />

				<NavChats
					chats={processedRecentChats}
					searchSpaceId={searchSpaceId}
					isSourcesExpanded={isSourcesExpanded}
				/>

				<NavNotes
					notes={processedRecentNotes}
					onAddNote={onAddNote}
					searchSpaceId={searchSpaceId}
					isSourcesExpanded={isSourcesExpanded}
				/>
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
