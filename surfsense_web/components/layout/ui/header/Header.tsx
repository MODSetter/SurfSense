"use client";

import { NotificationButton } from "@/components/notifications/NotificationButton";

interface HeaderProps {
	breadcrumb?: React.ReactNode;
	mobileMenuTrigger?: React.ReactNode;
}

export function Header({
	breadcrumb,
	mobileMenuTrigger,
}: HeaderProps) {
	return (
		<header className="sticky top-0 z-10 flex h-14 shrink-0 items-center gap-2 border-b bg-background/95 backdrop-blur supports-backdrop-filter:bg-background/60 px-4">
			{/* Left side - Mobile menu trigger + Breadcrumb */}
			<div className="flex flex-1 items-center gap-2 min-w-0">
				{mobileMenuTrigger}
				<div className="hidden md:block">{breadcrumb}</div>
			</div>

			{/* Right side - Actions */}
			<div className="flex items-center gap-2">
				{/* Notifications */}
				<NotificationButton />
			</div>
		</header>
	);
}
