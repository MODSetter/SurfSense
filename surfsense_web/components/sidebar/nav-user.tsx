"use client";

import { BadgeCheck, ChevronsUpDown, LogOut, Settings, User as UserIcon } from "lucide-react";
import { useParams, useRouter } from "next/navigation";
import { memo, useCallback, useEffect, useState } from "react";
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
import { apiClient } from "@/lib/api";

interface User {
	id: string;
	email: string;
	is_active: boolean;
	is_superuser: boolean;
	is_verified: boolean;
}

interface UserData {
	name: string;
	email: string;
	avatar: string;
}

// Memoized NavUser component for better performance
export const NavUser = memo(function NavUser() {
	const { isMobile } = useSidebar();
	const router = useRouter();
	const { search_space_id } = useParams();

	// User state management
	const [user, setUser] = useState<User | null>(null);
	const [isLoadingUser, setIsLoadingUser] = useState(true);
	const [userError, setUserError] = useState<string | null>(null);

	// Fetch user details
	useEffect(() => {
		const fetchUser = async () => {
			try {
				if (typeof window === "undefined") return;

				try {
					const userData = await apiClient.get<User>("users/me");
					setUser(userData);
					setUserError(null);
				} catch (error) {
					console.error("Error fetching user:", error);
					setUserError(error instanceof Error ? error.message : "Unknown error occurred");
				} finally {
					setIsLoadingUser(false);
				}
			} catch (error) {
				console.error("Error in fetchUser:", error);
				setIsLoadingUser(false);
			}
		};

		fetchUser();
	}, []);

	// Create user object for display
	const userData: UserData = {
		name: user?.email ? user.email.split("@")[0] : "User",
		email:
			user?.email ||
			(isLoadingUser ? "Loading..." : userError ? "Error loading user" : "Unknown User"),
		avatar: "/icon-128.png", // Default avatar
	};

	// Memoized logout handler
	const handleLogout = useCallback(() => {
		if (typeof window !== "undefined") {
			localStorage.removeItem("surfsense_bearer_token");
			router.push("/");
		}
	}, [router]);

	// Get user initials for avatar fallback
	const userInitials = userData.name
		.split(" ")
		.map((n: string) => n[0])
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
									<AvatarImage src={userData.avatar} alt={userData.name} />
									<AvatarFallback className="rounded-lg">
										{userInitials || <UserIcon className="h-4 w-4" />}
									</AvatarFallback>
								</Avatar>
								<div className="grid flex-1 text-left text-sm leading-tight">
									<span className="truncate font-medium">{userData.name}</span>
									<span className="truncate text-xs text-muted-foreground">{userData.email}</span>
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
										<AvatarImage src={userData.avatar} alt={userData.name} />
										<AvatarFallback className="rounded-lg">
											{userInitials || <UserIcon className="h-4 w-4" />}
										</AvatarFallback>
									</Avatar>
									<div className="grid flex-1 text-left text-sm leading-tight">
										<span className="truncate font-medium">{userData.name}</span>
										<span className="truncate text-xs text-muted-foreground">{userData.email}</span>
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
