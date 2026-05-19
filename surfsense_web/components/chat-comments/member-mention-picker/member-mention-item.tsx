"use client";

import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import type { MemberMentionItemProps } from "./types";

function getInitials(name: string | null, email: string): string {
	if (name) {
		return name
			.split(" ")
			.map((part) => part[0])
			.join("")
			.toUpperCase()
			.slice(0, 2);
	}
	return email[0]?.toUpperCase() ?? "?";
}

export function MemberMentionItem({
	member,
	isHighlighted,
	onSelect,
	onMouseEnter,
}: MemberMentionItemProps) {
	const displayName = member.displayName || member.email.split("@")[0];

	return (
		<Button
			variant="ghost"
			type="button"
			className={cn(
				"h-auto w-full justify-start gap-3 rounded-none px-3 py-2 text-left transition-colors",
				isHighlighted
					? "bg-primary/15 text-accent-foreground"
					: "hover:bg-accent hover:text-accent-foreground"
			)}
			onClick={() => onSelect(member)}
			onMouseEnter={onMouseEnter}
		>
			<Avatar className="size-7">
				{member.avatarUrl && <AvatarImage src={member.avatarUrl} alt={displayName} />}
				<AvatarFallback className="text-xs">
					{getInitials(member.displayName, member.email)}
				</AvatarFallback>
			</Avatar>
			<div className="flex min-w-0 flex-1 flex-col">
				<span className="truncate text-sm font-medium">{displayName}</span>
				<span className="truncate text-xs text-muted-foreground">{member.email}</span>
			</div>
		</Button>
	);
}
