"use client";

import {
	Bell,
	BellOff,
	ExternalLink,
	Info,
	type Megaphone,
	Rocket,
	Wrench,
	Zap,
} from "lucide-react";
import Link from "next/link";
import { useEffect } from "react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
	Card,
	CardContent,
	CardDescription,
	CardFooter,
	CardHeader,
	CardTitle,
} from "@/components/ui/card";
import type { AnnouncementCategory } from "@/contracts/types/announcement.types";
import { type AnnouncementWithState, useAnnouncements } from "@/hooks/use-announcements";
import { formatRelativeDate } from "@/lib/format-date";

// ---------------------------------------------------------------------------
// Category configuration
// ---------------------------------------------------------------------------

const categoryConfig: Record<
	AnnouncementCategory,
	{
		label: string;
		icon: typeof Megaphone;
		color: string;
		badgeVariant: "default" | "secondary" | "destructive" | "outline";
	}
> = {
	feature: {
		label: "Feature",
		icon: Rocket,
		color: "text-emerald-500",
		badgeVariant: "default",
	},
	update: {
		label: "Update",
		icon: Zap,
		color: "text-blue-500",
		badgeVariant: "secondary",
	},
	maintenance: {
		label: "Maintenance",
		icon: Wrench,
		color: "text-amber-500",
		badgeVariant: "outline",
	},
	info: {
		label: "Info",
		icon: Info,
		color: "text-muted-foreground",
		badgeVariant: "secondary",
	},
};

// ---------------------------------------------------------------------------
// Announcement card
// ---------------------------------------------------------------------------

function AnnouncementCard({ announcement }: { announcement: AnnouncementWithState }) {
	const config = categoryConfig[announcement.category] ?? categoryConfig.info;
	const Icon = config.icon;

	return (
		<Card className="group relative transition-all duration-200 hover:shadow-md">
			<CardHeader className="pb-3">
				<div className="flex items-start justify-between gap-3">
					<div className="flex items-start gap-3 min-w-0">
						<div
							className={`mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-muted ${config.color}`}
						>
							<Icon className="h-4 w-4" />
						</div>
						<div className="min-w-0 flex-1">
							<div className="flex items-center gap-2 flex-wrap">
								<CardTitle className="text-base leading-tight">{announcement.title}</CardTitle>
								<Badge variant={config.badgeVariant} className="text-[10px] px-1.5 py-0">
									{config.label}
								</Badge>
								{announcement.isImportant && (
									<Badge variant="destructive" className="text-[10px] px-1.5 py-0 gap-0.5">
										<Bell className="h-2.5 w-2.5" />
										Important
									</Badge>
								)}
							</div>
							<CardDescription className="mt-1 text-xs">
								{formatRelativeDate(announcement.date)}
							</CardDescription>
						</div>
					</div>
				</div>
			</CardHeader>

			<CardContent className="pb-3">
				<p className="text-sm text-muted-foreground leading-relaxed">{announcement.description}</p>
			</CardContent>

			{announcement.link && (
				<CardFooter className="pt-0 pb-4">
					<Button variant="outline" size="sm" asChild className="gap-1.5">
						<Link
							href={announcement.link.url}
							target={announcement.link.url.startsWith("http") ? "_blank" : undefined}
						>
							{announcement.link.label}
							<ExternalLink className="h-3 w-3" />
						</Link>
					</Button>
				</CardFooter>
			)}
		</Card>
	);
}

// ---------------------------------------------------------------------------
// Empty state
// ---------------------------------------------------------------------------

function EmptyState() {
	return (
		<div className="flex flex-col items-center justify-center py-16 text-center">
			<div className="flex h-16 w-16 items-center justify-center rounded-full bg-muted mb-4">
				<BellOff className="h-7 w-7 text-muted-foreground" />
			</div>
			<h3 className="text-lg font-semibold">No announcements</h3>
			<p className="mt-1 text-sm text-muted-foreground max-w-sm">
				You're all caught up! New announcements will appear here.
			</p>
		</div>
	);
}

// ---------------------------------------------------------------------------
// Page
// ---------------------------------------------------------------------------

export default function AnnouncementsPage() {
	const { announcements, markAllRead } = useAnnouncements();

	// Auto-mark all visible announcements as read when the page is opened
	useEffect(() => {
		markAllRead();
	}, [markAllRead]);

	return (
		<div className="min-h-screen relative pt-20">
			{/* Header */}
			<div className="border-b border-border/50">
				<div className="max-w-5xl mx-auto relative">
					<div className="p-6">
						<h1 className="text-4xl font-bold tracking-tight bg-linear-to-r from-gray-900 to-gray-600 dark:from-white dark:to-gray-400 bg-clip-text text-transparent">
							Announcements
						</h1>
					</div>
				</div>
			</div>

			{/* Content */}
			<div className="max-w-3xl mx-auto px-6 lg:px-10 pt-8 pb-20">
				{announcements.length === 0 ? (
					<EmptyState />
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
}
