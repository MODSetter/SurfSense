"use client";

import { Bell, ExternalLink, Info, type LucideIcon, Rocket, Wrench, Zap } from "lucide-react";
import Link from "next/link";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardFooter, CardHeader } from "@/components/ui/card";
import type { AnnouncementCategory } from "@/contracts/types/announcement.types";
import type { AnnouncementWithState } from "@/hooks/use-announcements";
import { formatRelativeDate } from "@/lib/format-date";

const categoryConfig: Record<
	AnnouncementCategory,
	{
		label: string;
		icon: LucideIcon;
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

export function AnnouncementCard({ announcement }: { announcement: AnnouncementWithState }) {
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
								<h2 className="text-base font-semibold leading-tight tracking-tight">
									{announcement.title}
								</h2>
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
