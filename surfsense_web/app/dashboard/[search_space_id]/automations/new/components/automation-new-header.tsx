"use client";
import { ArrowLeft, MessageSquarePlus } from "lucide-react";
import Link from "next/link";
import { Button } from "@/components/ui/button";

interface AutomationNewHeaderProps {
	searchSpaceId: number;
}

export function AutomationNewHeader({ searchSpaceId }: AutomationNewHeaderProps) {
	return (
		<div className="space-y-3">
			<Button asChild variant="ghost" size="sm" className="-ml-2 h-auto px-2 py-1">
				<Link
					href={`/dashboard/${searchSpaceId}/automations`}
					className="text-xs text-muted-foreground"
				>
					<ArrowLeft className="mr-1.5 h-3.5 w-3.5" />
					Back to automations
				</Link>
			</Button>

			<div className="flex items-start justify-between gap-4 flex-wrap">
				<div className="space-y-1">
					<h1 className="text-xl md:text-2xl font-semibold text-foreground">
						New automation · raw JSON
					</h1>
					<p className="text-sm text-muted-foreground max-w-2xl">
						Paste an ``AutomationCreate`` payload and submit. Validated against the schema before
						save. Prefer natural language? Use chat instead.
					</p>
				</div>
				<Button asChild variant="outline" size="sm">
					<Link href={`/dashboard/${searchSpaceId}/new-chat`}>
						<MessageSquarePlus className="mr-2 h-4 w-4" />
						Switch to chat
					</Link>
				</Button>
			</div>
		</div>
	);
}
