"use client";

import { BadgeCheck, LogOut, Settings, Shield, ShieldAlert } from "lucide-react";
import { useRouter } from "next/navigation";
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";
import { baseApiService } from "@/lib/apis/base-api.service";
import { AUTH_TOKEN_KEY } from "@/lib/constants";
import { CustomUser } from "@/contracts/types";
import { Button } from "@/components/ui/button";
import {
	DropdownMenu,
	DropdownMenuContent,
	DropdownMenuGroup,
	DropdownMenuItem,
	DropdownMenuLabel,
	DropdownMenuSeparator,
	DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";

interface UserDropdownProps {
	user: CustomUser;
	isAdmin?: boolean;
}

export function UserDropdown({ user, isAdmin = false }: UserDropdownProps) {
	const router = useRouter();

	const handleLogout = () => {
		try {
			if (typeof window !== "undefined") {
				localStorage.removeItem(AUTH_TOKEN_KEY);
				// Clear the baseApiService token to prevent stale auth state
				baseApiService.setBearerToken("");
				router.push("/");
			}
		} catch (error) {
			console.error("Error during logout:", error);
			// Optionally, provide user feedback
			if (typeof window !== "undefined") {
				alert("Logout failed. Please try again.");
				router.push("/");
			}
		}
	};

	return (
		<DropdownMenu>
			<DropdownMenuTrigger asChild>
				<Button variant="ghost" className="relative h-10 w-10 rounded-full">
					<Avatar className="h-8 w-8">
						<AvatarImage src={user.avatar} alt={user.name} />
						<AvatarFallback>{user.name.charAt(0)?.toUpperCase() || "?"}</AvatarFallback>
					</Avatar>
				</Button>
			</DropdownMenuTrigger>
			<DropdownMenuContent className="w-56" align="end" forceMount>
				<DropdownMenuLabel className="font-normal">
					<div className="flex flex-col space-y-1">
						<p className="text-sm font-medium leading-none">{user.name}</p>
						<p className="text-xs leading-none text-muted-foreground">{user.email}</p>
					</div>
				</DropdownMenuLabel>
				<DropdownMenuSeparator />
				<DropdownMenuGroup>
					<DropdownMenuItem onClick={() => router.push(`/dashboard/api-key`)}>
						<BadgeCheck className="mr-2 h-4 w-4" />
						API Key
					</DropdownMenuItem>
					<DropdownMenuItem onClick={() => router.push(`/dashboard/security`)}>
						<Shield className="mr-2 h-4 w-4" />
						Security (2FA)
					</DropdownMenuItem>
					<DropdownMenuItem onClick={() => router.push(`/dashboard/rate-limiting`)}>
						<ShieldAlert className="mr-2 h-4 w-4" />
						Rate Limiting
					</DropdownMenuItem>
					{isAdmin && (
						<DropdownMenuItem onClick={() => router.push(`/dashboard/site-settings`)}>
							<Settings className="mr-2 h-4 w-4" />
							Site Settings
						</DropdownMenuItem>
					)}
				</DropdownMenuGroup>
				<DropdownMenuSeparator />
				<DropdownMenuItem onClick={handleLogout}>
					<LogOut className="mr-2 h-4 w-4" />
					Log out
				</DropdownMenuItem>
			</DropdownMenuContent>
		</DropdownMenu>
	);
}
