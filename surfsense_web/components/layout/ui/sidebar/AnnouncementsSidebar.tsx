"use client";

import { ChevronLeft } from "lucide-react";
import { useEffect } from "react";
import { AnnouncementsEmptyState } from "@/components/announcements/AnnouncementsEmptyState";
import { AnnouncementCard } from "@/components/announcements/AnnouncementCard";
import { Button } from "@/components/ui/button";
import { useAnnouncements } from "@/hooks/use-announcements";
import { useMediaQuery } from "@/hooks/use-media-query";
import { SidebarSlideOutPanel } from "./SidebarSlideOutPanel";

interface AnnouncementsSidebarProps {
	open: boolean;
	onOpenChange: (open: boolean) => void;
	onCloseMobileSidebar?: () => void;
}

export function AnnouncementsSidebar({
	open,
	onOpenChange,
	onCloseMobileSidebar,
}: AnnouncementsSidebarProps) {
	const isMobile = !useMediaQuery("(min-width: 640px)");
	const { announcements, markAllRead } = useAnnouncements();

	useEffect(() => {
		if (!open) return;
		markAllRead();
	}, [open, markAllRead]);

	const body = (
		<div className="h-full flex flex-col">
			<div className="shrink-0 p-4 pb-2 space-y-3">
				<div className="flex items-center justify-between">
					<div className="flex items-center gap-2">
						{isMobile && (
							<Button
								variant="ghost"
								size="icon"
								className="h-8 w-8 rounded-full"
								onClick={() => {
									onOpenChange(false);
									onCloseMobileSidebar?.();
								}}
							>
								<ChevronLeft className="h-4 w-4 text-muted-foreground" />
								<span className="sr-only">Close</span>
							</Button>
						)}
						<h2 className="text-lg font-semibold">Announcements</h2>
					</div>
				</div>
			</div>

			<div className="flex-1 overflow-y-auto p-4">
				{announcements.length === 0 ? (
					<AnnouncementsEmptyState />
				) : (
					<div className="flex flex-col gap-4">
						{announcements.map((announcement) => (
							<AnnouncementCard key={announcement.id} announcement={announcement} />
						))}
					</div>
				)}
			</div>
		</div>
	);

	return (
		<SidebarSlideOutPanel open={open} onOpenChange={onOpenChange} ariaLabel="Announcements">
			{body}
		</SidebarSlideOutPanel>
	);
}

