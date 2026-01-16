"use client";

import { Loader2 } from "lucide-react";
import { ScrollArea } from "@/components/ui/scroll-area";
import { MemberMentionItem } from "./member-mention-item";
import type { MemberMentionPickerProps } from "./types";

export function MemberMentionPicker({
	members,
	query,
	highlightedIndex,
	isLoading = false,
	onSelect,
	onHighlightChange,
}: MemberMentionPickerProps) {
	const filteredMembers = query
		? members.filter(
				(member) =>
					member.displayName?.toLowerCase().includes(query.toLowerCase()) ||
					member.email.toLowerCase().includes(query.toLowerCase())
			)
		: members;

	if (isLoading) {
		return (
			<div className="flex items-center justify-center py-6">
				<Loader2 className="size-5 animate-spin text-muted-foreground" />
			</div>
		);
	}

	if (filteredMembers.length === 0) {
		return (
			<div className="px-3 py-6 text-center text-sm text-muted-foreground">
				{query ? "No members found" : "No members available"}
			</div>
		);
	}

	return (
		<ScrollArea className="max-h-64">
			<div className="py-1">
				{filteredMembers.map((member, index) => (
					<MemberMentionItem
						key={member.id}
						member={member}
						isHighlighted={index === highlightedIndex}
						onSelect={onSelect}
						onMouseEnter={() => onHighlightChange(index)}
					/>
				))}
			</div>
		</ScrollArea>
	);
}
