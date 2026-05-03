"use client";

import { useAtom } from "jotai";
import { useEffect } from "react";
import { announcementsDialogAtom } from "@/atoms/settings/settings-dialog.atoms";
import { AnnouncementCard } from "@/components/announcements/AnnouncementCard";
import { AnnouncementsEmptyState } from "@/components/announcements/AnnouncementsEmptyState";
import { Dialog, DialogContent, DialogTitle } from "@/components/ui/dialog";
import { Separator } from "@/components/ui/separator";
import { useAnnouncements } from "@/hooks/use-announcements";

export function AnnouncementsDialog() {
	const [open, setOpen] = useAtom(announcementsDialogAtom);
	const { announcements, markAllRead } = useAnnouncements();

	// Auto-mark all visible announcements as read when the dialog opens
	useEffect(() => {
		if (open) {
			markAllRead();
		}
	}, [open, markAllRead]);

	return (
		<Dialog open={open} onOpenChange={setOpen}>
			<DialogContent className="select-none max-w-[900px] w-[95vw] md:w-[90vw] h-[90vh] md:h-[80vh] max-h-[640px] flex flex-col p-0 gap-0 overflow-hidden [--card:var(--background)] dark:[--card:oklch(0.205_0_0)] dark:[--background:oklch(0.205_0_0)]">
				<DialogTitle className="sr-only">What's New</DialogTitle>

				<div className="flex flex-1 flex-col overflow-hidden min-w-0">
					<div className="px-6 md:px-8 pt-6 pb-2 shrink-0">
						<h2 className="text-lg font-semibold">What's New</h2>
						<Separator className="mt-4" />
					</div>
					<div className="flex-1 overflow-y-auto overflow-x-hidden">
						<div className="px-4 md:px-8 pt-4 pb-6 min-w-0">
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
				</div>
			</DialogContent>
		</Dialog>
	);
}
