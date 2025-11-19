"use client";

import { Logo } from "@/components/Logo";
import { ThemeTogglerComponent } from "@/components/theme/theme-toggle";
import { UserDropdown } from "@/components/UserDropdown";
import { CustomUser } from "@/contracts/types";

interface DashboardHeaderProps {
	title: string;
	description: string;
	user: CustomUser;
	isAdmin?: boolean;
}

export function DashboardHeader({ title, description, user, isAdmin = false }: DashboardHeaderProps) {
	return (
		<div className="flex flex-row space-x-4 justify-between">
			<div className="flex flex-row space-x-4">
				<Logo className="w-10 h-10 rounded-md" href="/dashboard" />
				<div className="flex flex-col space-y-2">
					<h1 className="text-4xl font-bold">{title}</h1>
					<p className="text-muted-foreground">{description}</p>
				</div>
			</div>
			<div className="flex items-center space-x-3">
				<UserDropdown user={user} isAdmin={isAdmin} />
				<ThemeTogglerComponent />
			</div>
		</div>
	);
}
