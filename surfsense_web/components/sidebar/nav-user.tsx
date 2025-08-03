"use client";

import { BadgeCheck, ChevronsUpDown, LogOut, Settings, User } from "lucide-react";
import { useParams, useRouter } from "next/navigation";
import { memo, useCallback } from "react";
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";
import {
	DropdownMenu,
	DropdownMenuContent,
	DropdownMenuGroup,
	DropdownMenuItem,
	DropdownMenuLabel,
	DropdownMenuSeparator,
	DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import {
	SidebarGroup,
	SidebarMenu,
	SidebarMenuButton,
	SidebarMenuItem,
	useSidebar,
} from "@/components/ui/sidebar";

interface UserData {
	name: string;
	email: string;
	avatar: string;
}

// Memoized NavUser component for better performance
export const NavUser = memo(function NavUser({ user }: { user: UserData }) {
	const { isMobile } = useSidebar();
	const router = useRouter();
	const { search_space_id } = useParams();

	// Memoized logout handler
	const handleLogout = useCallback(() => {
		if (typeof window !== "undefined") {
			localStorage.removeItem("surfsense_bearer_token");
			router.push("/");
		}
	}, [router]);

	// Get user initials for avatar fallback
	const userInitials = user.name
		.split(" ")
		.map((n) => n[0])
		.join("")
		.toUpperCase()
		.slice(0, 2);

	return (
		<SidebarGroup className="mt-auto">
			<SidebarMenu>
				<SidebarMenuItem>
					<DropdownMenu>
						<DropdownMenuTrigger asChild>
							<SidebarMenuButton
								size="lg"
								className="data-[state=open]:bg-sidebar-accent data-[state=open]:text-sidebar-accent-foreground"
								aria-label="User menu"
							>
								<Avatar className="h-8 w-8 rounded-lg">
									<AvatarImage src={user.avatar} alt={user.name} />
									<AvatarFallback className="rounded-lg">
										{userInitials || <User className="h-4 w-4" />}
									</AvatarFallback>
								</Avatar>
								<div className="grid flex-1 text-left text-sm leading-tight">
									<span className="truncate font-medium">{user.name}</span>
									<span className="truncate text-xs text-muted-foreground">{user.email}</span>
								</div>
								<ChevronsUpDown className="ml-auto size-4" />
							</SidebarMenuButton>
						</DropdownMenuTrigger>
						<DropdownMenuContent
							className="w-(--radix-dropdown-menu-trigger-width) min-w-56 rounded-lg"
							side={isMobile ? "bottom" : "right"}
							align="end"
							sideOffset={4}
						>
							<DropdownMenuLabel className="p-0 font-normal">
								<div className="flex items-center gap-2 px-1 py-1.5 text-left text-sm">
									<Avatar className="h-8 w-8 rounded-lg">
										<AvatarImage src={user.avatar} alt={user.name} />
										<AvatarFallback className="rounded-lg">
											{userInitials || <User className="h-4 w-4" />}
										</AvatarFallback>
									</Avatar>
									<div className="grid flex-1 text-left text-sm leading-tight">
										<span className="truncate font-medium">{user.name}</span>
										<span className="truncate text-xs text-muted-foreground">{user.email}</span>
									</div>
								</div>
							</DropdownMenuLabel>
							<DropdownMenuSeparator />
							<DropdownMenuGroup>
								<DropdownMenuItem
									onClick={() => router.push(`/dashboard/${search_space_id}/api-key`)}
									aria-label="Manage API key"
								>
									<BadgeCheck className="h-4 w-4" />
									API Key
								</DropdownMenuItem>
							</DropdownMenuGroup>
							<DropdownMenuSeparator />
							<DropdownMenuItem
								onClick={() => router.push(`/settings`)}
								aria-label="Go to settings"
							>
								<Settings className="h-4 w-4" />
								Settings
							</DropdownMenuItem>
							<DropdownMenuItem
								onClick={handleLogout}
								aria-label="Sign out"
								className="text-destructive focus:text-destructive"
							>
								<LogOut className="h-4 w-4" />
								Sign out
							</DropdownMenuItem>
						</DropdownMenuContent>
					</DropdownMenu>
				</SidebarMenuItem>
			</SidebarMenu>
		</SidebarGroup>
	);
});
