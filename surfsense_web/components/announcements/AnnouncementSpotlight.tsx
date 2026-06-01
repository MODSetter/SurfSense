"use client";

import { ExternalLink } from "lucide-react";
import Image from "next/image";
import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { Button } from "@/components/ui/button";
import {
	Dialog,
	DialogContent,
	DialogDescription,
	DialogFooter,
	DialogTitle,
} from "@/components/ui/dialog";
import { useAnnouncements } from "@/hooks/use-announcements";

/**
 * Proactively shows important "spotlight" announcements in a blocking dialog.
 *
 * Behaviour:
 * - On load, the first active, audience-matched, unread spotlight announcement
 *   is shown automatically.
 * - The user must explicitly acknowledge it ("Got it" or the CTA link), which
 *   marks it as read so it never shows again.
 * - Closing via the X / Escape / outside-click only hides it for the current
 *   session; it reappears on the next load until the user marks it as seen.
 */
export function AnnouncementSpotlight() {
	const { announcements, markRead } = useAnnouncements();
	const [sessionDismissed, setSessionDismissed] = useState<Set<string>>(() => new Set());
	const [ready, setReady] = useState(false);

	// Short delay so the spotlight doesn't flash during initial hydration/layout.
	useEffect(() => {
		const timer = setTimeout(() => setReady(true), 800);
		return () => clearTimeout(timer);
	}, []);

	const current = useMemo(
		() =>
			announcements.find(
				(a) => a.spotlight && a.isImportant && !a.isRead && !sessionDismissed.has(a.id)
			) ?? null,
		[announcements, sessionDismissed]
	);

	if (!current) return null;

	const handleAcknowledge = () => {
		markRead(current.id);
	};

	const handleOpenChange = (next: boolean) => {
		if (!next) {
			setSessionDismissed((prev) => {
				const updated = new Set(prev);
				updated.add(current.id);
				return updated;
			});
		}
	};

	return (
		<Dialog open={ready} onOpenChange={handleOpenChange}>
			<DialogContent className="max-w-md gap-0 overflow-hidden p-0">
				{current.image && (
					<div className="relative aspect-video w-full border-b bg-muted">
						<Image
							src={current.image.src}
							alt={current.image.alt}
							fill
							sizes="(max-width: 768px) 95vw, 448px"
							className="object-cover"
							priority
						/>
					</div>
				)}
				<div className="flex flex-col gap-3 p-6">
					<DialogTitle className="text-xl">{current.title}</DialogTitle>
					<DialogDescription className="text-sm leading-relaxed text-muted-foreground">
						{current.description}
					</DialogDescription>
					<DialogFooter className="mt-2">
						{current.link && (
							<Button variant="outline" asChild className="gap-1.5" onClick={handleAcknowledge}>
								<Link
									href={current.link.url}
									target={current.link.url.startsWith("http") ? "_blank" : undefined}
								>
									{current.link.label}
									<ExternalLink className="h-3.5 w-3.5" />
								</Link>
							</Button>
						)}
						<Button onClick={handleAcknowledge}>Got it</Button>
					</DialogFooter>
				</div>
			</DialogContent>
		</Dialog>
	);
}
