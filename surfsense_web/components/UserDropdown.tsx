"use client";

import { BadgeCheck, LogOut } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
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
import { Spinner } from "@/components/ui/spinner";
import { getLoginPath, logout } from "@/lib/auth-utils";
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
	const [isLoggingOut, setIsLoggingOut] = useState(false);

	const handleLogout = async () => {
		if (isLoggingOut) return;
		setIsLoggingOut(true);
		try {
			trackLogout();
			resetUser();

			await logout();

			router.push("/");
			router.refresh();
			if (typeof window !== "undefined") {
				window.location.href = getLoginPath();
			}
		} catch (error) {
			console.error("Error during logout:", error);
			await logout();
			router.push("/");
			router.refresh();
			if (typeof window !== "undefined") {
				window.location.href = getLoginPath();
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
			<DropdownMenuContent className="w-44 md:w-56" align="end">
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
					<DropdownMenuItem asChild className="text-xs md:text-sm">
						<Link href="/dashboard/api-key">
							<BadgeCheck className="mr-2 h-3.5 w-3.5 md:h-4 md:w-4" />
							API Key
						</Link>
					</DropdownMenuItem>
				</DropdownMenuGroup>
				<DropdownMenuSeparator />
				<DropdownMenuItem
					onClick={handleLogout}
					className="text-xs md:text-sm"
					disabled={isLoggingOut}
				>
					{isLoggingOut ? (
						<Spinner size="sm" className="mr-2" />
					) : (
						<LogOut className="mr-2 h-3.5 w-3.5 md:h-4 md:w-4" />
					)}
					{isLoggingOut ? "Logging out..." : "Log out"}
				</DropdownMenuItem>
			</DropdownMenuContent>
		</DropdownMenu>
	);
}
