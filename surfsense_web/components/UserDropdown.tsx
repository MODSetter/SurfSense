"use client";

import { BadgeCheck, LogOut } from "lucide-react";
import { useRouter } from "next/navigation";
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";
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
import { cleanupElectric } from "@/lib/electric/client";
import { resetUser, trackLogout } from "@/lib/posthog/events";

export function UserDropdown({
	user,
}: {
	user: {
		name: string;
		email: string;
		avatar: string;
	};
}) {
	const router = useRouter();

	const handleLogout = async () => {
		try {
			// Track logout event and reset PostHog identity
			trackLogout();
			resetUser();

			// Best-effort cleanup of Electric SQL / PGlite
			// Even if this fails, login-time cleanup will handle it
			try {
				await cleanupElectric();
			} catch (err) {
				console.warn("[Logout] Electric cleanup failed (will be handled on next login):", err);
			}

			if (typeof window !== "undefined") {
				localStorage.removeItem("surfsense_bearer_token");
				window.location.href = "/";
			}
		} catch (error) {
			console.error("Error during logout:", error);
			// Optionally, provide user feedback
			if (typeof window !== "undefined") {
				localStorage.removeItem("surfsense_bearer_token");
				window.location.href = "/";
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
			<DropdownMenuContent className="w-44 md:w-56" align="end" forceMount>
				<DropdownMenuLabel className="font-normal p-2 md:p-3">
					<div className="flex flex-col space-y-1">
						<p className="text-xs md:text-sm font-medium leading-none">{user.name}</p>
						<p className="text-[10px] md:text-xs leading-none text-muted-foreground">
							{user.email}
						</p>
					</div>
				</DropdownMenuLabel>
				<DropdownMenuSeparator />
				<DropdownMenuGroup>
					<DropdownMenuItem
						onClick={() => router.push(`/dashboard/api-key`)}
						className="text-xs md:text-sm"
					>
						<BadgeCheck className="mr-2 h-3.5 w-3.5 md:h-4 md:w-4" />
						API Key
					</DropdownMenuItem>
				</DropdownMenuGroup>
				<DropdownMenuSeparator />
				<DropdownMenuItem onClick={handleLogout} className="text-xs md:text-sm">
					<LogOut className="mr-2 h-3.5 w-3.5 md:h-4 md:w-4" />
					Log out
				</DropdownMenuItem>
			</DropdownMenuContent>
		</DropdownMenu>
	);
}
