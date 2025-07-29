"use client";

import type React from "react";
import { AppSidebarProvider } from "@/components/sidebar/AppSidebarProvider";
import { ThemeTogglerComponent } from "@/components/theme/theme-toggle";
import { Separator } from "@/components/ui/separator";
import { SidebarInset, SidebarProvider, SidebarTrigger } from "@/components/ui/sidebar";

export function DashboardClientLayout({
	children,
	searchSpaceId,
	navSecondary,
	navMain,
}: {
	children: React.ReactNode;
	searchSpaceId: string;
	navSecondary: any[];
	navMain: any[];
}) {
	return (
		<SidebarProvider>
			{/* Use AppSidebarProvider which fetches user, search space, and recent chats */}
			<AppSidebarProvider
				searchSpaceId={searchSpaceId}
				navSecondary={navSecondary}
				navMain={navMain}
			/>
			<SidebarInset>
				<header className="flex h-16 shrink-0 items-center gap-2">
					<div className="flex items-center gap-2 px-4">
						<SidebarTrigger className="-ml-1" />
						<Separator orientation="vertical" className="h-6" />
						<ThemeTogglerComponent />
					</div>
				</header>
				{children}
			</SidebarInset>
		</SidebarProvider>
	);
}
