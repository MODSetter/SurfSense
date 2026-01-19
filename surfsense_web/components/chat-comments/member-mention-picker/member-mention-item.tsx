"use client";

import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";
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
		<button
			type="button"
			className={cn(
				"flex w-full items-center gap-3 px-3 py-2 text-left transition-colors",
				isHighlighted ? "bg-accent" : "hover:bg-accent/50"
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
		</button>
	);
}
