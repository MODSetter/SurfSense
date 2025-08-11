"use client";

import type React from "react";
import { useState } from "react";
import { DashboardBreadcrumb } from "@/components/dashboard-breadcrumb";
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
	const [open, setOpen] = useState<boolean>(() => {
		try {
			const match = document.cookie.match(/(?:^|; )sidebar_state=([^;]+)/);
			if (match) return match[1] === "true";
		} catch {
			// ignore
		}
		return true;
	});

	return (
		<SidebarProvider open={open} onOpenChange={setOpen}>
			{/* Use AppSidebarProvider which fetches user, search space, and recent chats */}
			<AppSidebarProvider
				searchSpaceId={searchSpaceId}
				navSecondary={navSecondary}
				navMain={navMain}
			/>
			<SidebarInset>
				<header className="sticky top-0 z-50 flex h-16 shrink-0 items-center gap-2 bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/60 border-b">
					<div className="flex items-center justify-between w-full gap-2 px-4">
						<div className="flex items-center gap-2">
							<SidebarTrigger className="-ml-1" />
							<Separator orientation="vertical" className="h-6" />
							<DashboardBreadcrumb />
						</div>
						<ThemeTogglerComponent />
					</div>
				</header>
				{children}
			</SidebarInset>
		</SidebarProvider>
	);
}
