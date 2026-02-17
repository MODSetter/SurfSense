"use client";

import {
	Bell,
	BellOff,
	CheckCheck,
	ExternalLink,
	Filter,
	Info,
	type Megaphone,
	Rocket,
	Wrench,
	X,
	Zap,
} from "lucide-react";
import Link from "next/link";
import { useState } from "react";
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
import {
	DropdownMenu,
	DropdownMenuCheckboxItem,
	DropdownMenuContent,
	DropdownMenuLabel,
	DropdownMenuSeparator,
	DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Separator } from "@/components/ui/separator";
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "@/components/ui/tooltip";
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

function AnnouncementCard({
	announcement,
	onMarkRead,
	onDismiss,
}: {
	announcement: AnnouncementWithState;
	onMarkRead: (id: string) => void;
	onDismiss: (id: string) => void;
}) {
	const config = categoryConfig[announcement.category];
	const Icon = config.icon;

	return (
		<Card
			className={`group relative transition-all duration-200 hover:shadow-md ${
				!announcement.isRead ? "border-l-4 border-l-primary bg-primary/2" : ""
			}`}
		>
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
								{!announcement.isRead && (
									<span className="h-2 w-2 rounded-full bg-primary shrink-0" />
								)}
							</div>
							<CardDescription className="mt-1 text-xs">
								{formatRelativeDate(announcement.date)}
							</CardDescription>
						</div>
					</div>

					{/* Actions */}
					<div className="flex items-center gap-1 shrink-0 opacity-0 group-hover:opacity-100 transition-opacity">
						{!announcement.isRead && (
							<Tooltip>
								<TooltipTrigger asChild>
									<Button
										variant="ghost"
										size="icon"
										className="h-7 w-7"
										onClick={() => onMarkRead(announcement.id)}
									>
										<CheckCheck className="h-3.5 w-3.5" />
									</Button>
								</TooltipTrigger>
								<TooltipContent>Mark as read</TooltipContent>
							</Tooltip>
						)}
						<Tooltip>
							<TooltipTrigger asChild>
								<Button
									variant="ghost"
									size="icon"
									className="h-7 w-7"
									onClick={() => onDismiss(announcement.id)}
								>
									<X className="h-3.5 w-3.5" />
								</Button>
							</TooltipTrigger>
							<TooltipContent>Dismiss</TooltipContent>
						</Tooltip>
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
							onClick={() => onMarkRead(announcement.id)}
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

function EmptyState({ hasFilters }: { hasFilters: boolean }) {
	return (
		<div className="flex flex-col items-center justify-center py-16 text-center">
			<div className="flex h-16 w-16 items-center justify-center rounded-full bg-muted mb-4">
				{hasFilters ? (
					<Filter className="h-7 w-7 text-muted-foreground" />
				) : (
					<BellOff className="h-7 w-7 text-muted-foreground" />
				)}
			</div>
			<h3 className="text-lg font-semibold">
				{hasFilters ? "No matching announcements" : "No announcements"}
			</h3>
			<p className="mt-1 text-sm text-muted-foreground max-w-sm">
				{hasFilters
					? "Try adjusting your filters to see more announcements."
					: "You're all caught up! New announcements will appear here."}
			</p>
		</div>
	);
}

// ---------------------------------------------------------------------------
// Page
// ---------------------------------------------------------------------------

export default function AnnouncementsPage() {
	const [activeCategories, setActiveCategories] = useState<AnnouncementCategory[]>([]);
	const [showOnlyUnread, setShowOnlyUnread] = useState(false);

	const { announcements, unreadCount, markRead, markAllRead, dismiss } = useAnnouncements({
		includeDismissed: false,
	});

	// Apply local filters
	const filteredAnnouncements = announcements.filter((a) => {
		if (activeCategories.length > 0 && !activeCategories.includes(a.category)) return false;
		if (showOnlyUnread && a.isRead) return false;
		return true;
	});

	const hasActiveFilters = activeCategories.length > 0 || showOnlyUnread;

	const toggleCategory = (cat: AnnouncementCategory) => {
		setActiveCategories((prev) =>
			prev.includes(cat) ? prev.filter((c) => c !== cat) : [...prev, cat]
		);
	};

	return (
		<TooltipProvider delayDuration={0}>
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
					{/* Toolbar */}
					<div className="flex items-center justify-between gap-3 mb-6">
						<div className="flex items-center gap-2">
							{/* Category filter dropdown */}
							<DropdownMenu>
								<DropdownMenuTrigger asChild>
									<Button variant="outline" size="sm" className="gap-1.5">
										<Filter className="h-3.5 w-3.5" />
										Filter
										{activeCategories.length > 0 && (
											<Badge variant="secondary" className="ml-1 px-1.5 py-0 text-[10px]">
												{activeCategories.length}
											</Badge>
										)}
									</Button>
								</DropdownMenuTrigger>
								<DropdownMenuContent align="start" className="w-48">
									<DropdownMenuLabel>Categories</DropdownMenuLabel>
									<DropdownMenuSeparator />
									{(Object.keys(categoryConfig) as AnnouncementCategory[]).map((cat) => {
										const cfg = categoryConfig[cat];
										const CatIcon = cfg.icon;
										return (
											<DropdownMenuCheckboxItem
												key={cat}
												checked={activeCategories.includes(cat)}
												onCheckedChange={() => toggleCategory(cat)}
											>
												<CatIcon className={`mr-2 h-3.5 w-3.5 ${cfg.color}`} />
												{cfg.label}
											</DropdownMenuCheckboxItem>
										);
									})}
									<DropdownMenuSeparator />
									<DropdownMenuCheckboxItem
										checked={showOnlyUnread}
										onCheckedChange={() => setShowOnlyUnread((v) => !v)}
									>
										<Bell className="mr-2 h-3.5 w-3.5" />
										Unread only
									</DropdownMenuCheckboxItem>
								</DropdownMenuContent>
							</DropdownMenu>

							{hasActiveFilters && (
								<Button
									variant="ghost"
									size="sm"
									className="text-xs text-muted-foreground"
									onClick={() => {
										setActiveCategories([]);
										setShowOnlyUnread(false);
									}}
								>
									Clear filters
								</Button>
							)}
						</div>

						{/* Mark all read */}
						{unreadCount > 0 && (
							<Button variant="ghost" size="sm" className="gap-1.5 text-xs" onClick={markAllRead}>
								<CheckCheck className="h-3.5 w-3.5" />
								Mark all as read
								<Badge variant="secondary" className="ml-1 px-1.5 py-0 text-[10px]">
									{unreadCount}
								</Badge>
							</Button>
						)}
					</div>

					<Separator className="mb-6" />

					{/* Announcement list */}
					{filteredAnnouncements.length === 0 ? (
						<EmptyState hasFilters={hasActiveFilters} />
					) : (
						<div className="flex flex-col gap-4">
							{filteredAnnouncements.map((announcement) => (
								<AnnouncementCard
									key={announcement.id}
									announcement={announcement}
									onMarkRead={markRead}
									onDismiss={dismiss}
								/>
							))}
						</div>
					)}
				</div>
			</div>
		</TooltipProvider>
	);
}
